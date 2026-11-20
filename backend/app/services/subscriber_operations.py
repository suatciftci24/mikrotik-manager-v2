"""Committed daily-operation audit receipts and separate skip outcomes."""
from datetime import datetime,date,timedelta,timezone
from zoneinfo import ZoneInfo
import hashlib,json,re
from uuid import UUID, uuid5
from sqlalchemy import select,func,case,literal,union_all
from sqlalchemy.orm import aliased
from app.core.authorization import require_workspace_account,workspace_can_manage,workspace_scope
from app.core.database import SessionLocal
from app.core.v26_acceptance import local_undo_enabled
from app.models.subscriber_workspace import SyntheticSubscriber as Account,SyntheticSubscriberEvent as Event, SyntheticSubscriberSkip as Skip
from app.services.subscriber_center import SubscriberWorkspace,request_audit,event_scope,event_source
from app.services.router_workspace import guard,boundary,WorkspaceError,require_active_router
from app.models.router_workspace import RouterWorkspaceRecord

PUBLIC_FIELDS={'customer_name','plan','status','expires_on','started_on','router_id','username','access_type','source','package_id','package_revision'}
DAILY_REPORT_OPERATIONS=('EXTEND','PLAN','STATUS','UNDO')
UNDO_PREVIEW_FIELDS={'EDIT':'customer_name','STATUS':'status','EXTEND':'expires_on','EXPIRE':'expires_on'}

def fingerprint(command,actor):
    values=command.model_dump(mode='json')
    for key in ('package_id','package_revision','expected_status'):
        if key not in command.model_fields_set:values.pop(key,None)
    return hashlib.sha256(json.dumps([actor,values],sort_keys=True,separators=(',',':')).encode()).hexdigest()

def group_id_for_requests(request_ids, actor):
    if len(request_ids) < 2:
        return None
    members = sorted(str(id) for id in request_ids)
    return str(uuid5(UUID('663ba438-5a2c-4dd0-abfa-536c619ee187'), json.dumps([actor, members])))


def bulk_group_id(entries, actor):
    return group_id_for_requests([entry.request_id for entry in entries], actor)


def lock_operation_request(session, request_id):
    # Audit and skip outcomes share an idempotency key across two tables.
    if session.bind.dialect.name == 'postgresql':
        key = int.from_bytes(hashlib.sha256(request_id.bytes).digest()[:8], 'big', signed=True)
        session.execute(select(func.pg_advisory_xact_lock(key)))


def execution_metadata(group_id):
    return {'group_id': group_id, 'execution_type': 'BULK' if group_id else 'SINGLE'}


def public_changes(changes,key):
    return {name:(None if change.get(key) is None else str(change[key])) for name,change in changes.items() if name in PUBLIC_FIELDS and isinstance(change,dict)}

def event_receipt(event, *, skipped=False):
    stored=event.changes.get('_management',{}).get('receipt')
    if stored:
        if event.operation == 'UNDO':
            origin = event.changes.get('_undo', {})
            if not origin.get('source_request_id') or any(stored.get(key) != origin.get(key)
                    for key in ('source_request_id', 'source_group_id')):
                raise WorkspaceError(409, 'Geri alma işleminin kaynak audit kaydı uyuşmuyor.')
        # History must obey the same canonical audit identity as UUID recovery.
        expected=dict(item_id=event.subscriber_id,request_id=event.id,actor_id=event.actor_id,
                      revision=event.revision,operation=event.operation,occurred_at=event.occurred_at,
                      previous=public_changes(event.changes,'previous'),values=public_changes(event.changes,'new'))
        if (stored.get('recorded') is not (not skipped) or stored.get('skipped', False) is not skipped
                or type(stored.get('success')) is not bool
                or (skipped and (event.operation != 'STATUS' or stored['success'] or stored.get('error') is not None
                                 or expected['previous'] != expected['values'] or expected['values'].get('status') not in ('ACTIVE','PAUSED')))
                or any(stored.get(key)!=value for key,value in expected.items())
                or (stored.get('router_id')!=stored.get('previous_router_id') if event.operation!='ROUTER' or not stored['success']
                    else stored.get('router_id')!=stored['values'].get('router_id') or stored.get('previous_router_id')!=stored['previous'].get('router_id'))):
            raise WorkspaceError(409,'İşlem geçmişinin audit kanıtı uyuşmuyor; kayıt başarı sayılmadı.')
        return stored
    if skipped:
        raise WorkspaceError(409, 'Atlama sonuç kaydı doğrulanamadı.')
    previous=public_changes(event.changes,'previous');values=public_changes(event.changes,'new')
    return dict(item_id=event.subscriber_id,request_id=event.id,success=True,recorded=True,operation=event.operation,actor_id=event.actor_id,
                router_id=event.changes.get('_router_id',values.get('router_id')),previous_router_id=previous.get('router_id'),previous=previous,values=values,occurred_at=event.occurred_at,revision=event.revision,error=None)

def undo_source_group(receipt):
    group = receipt.get('group_id')
    mode = receipt.get('execution_type')
    if group is None and mode in (None, 'SINGLE'):
        return None
    # Older single receipts may omit both fields. Declared bulk receipts must carry a group.
    if mode == 'BULK' and isinstance(group, str):
        try:
            if str(UUID(group)) == group:
                return group
        except ValueError:
            pass
    raise WorkspaceError(409, 'Kaynak işlemin grup bilgisi doğrulanamadı. Geri alma uygulanmadı.')


def valid_previous_value(field, value, account):
    if field == 'status':
        return value in ('ACTIVE', 'PAUSED')
    if field == 'customer_name':
        return value is not None and 2 <= len(value) <= 160 and value.isprintable() and value.strip() == value
    if value is None:
        return True
    try:
        previous = date.fromisoformat(value)
        started = account.fields.get('started_on')
        return previous.isoformat() == value and (not started or previous >= date.fromisoformat(started))
    except (TypeError, ValueError):
        return False


class SubscriberOperationsService:
    def __init__(self,sessions=SessionLocal,check=guard):self.sessions=sessions;self.check=check
    @staticmethod
    def prior(session,command,actor,user=None,group_id=None):
        request_id = str(command.request_id)
        prior = session.get(Event, request_id)
        if prior is None or '_management' not in prior.changes:
            prior = session.get(Skip, request_id) or prior
        if prior:
            if prior.actor_id!=actor or prior.changes.get('_management',{}).get('fingerprint')!=fingerprint(command,actor):raise WorkspaceError(409,'İstek kimliği başka bir işleme ait. Yeni önizleme oluşturun.')
            receipt=event_receipt(prior, skipped=isinstance(prior, Skip))
            if receipt.get('group_id') != group_id:
                raise WorkspaceError(409, 'İstek kimliği başka bir işlem grubuna ait.')
            if user is not None:
                from app.core.authorization import require_workspace_router
                for key in ('router_id','previous_router_id'):
                    if receipt.get(key):require_workspace_router(user,receipt[key])
            return receipt
    @boundary
    def execute_bulk(self, entries, actor, user):
        group_id = bulk_group_id(entries, actor)
        with self.sessions.begin() as session:
            self.check(session)
            if session.get_bind().dialect.name == 'sqlite':
                # Start the outer transaction before any savepoint in the synthetic store.
                session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            for entry in sorted(entries, key=lambda entry: entry.request_id):
                lock_operation_request(session, entry.request_id)
            for entry in entries:
                row = session.get(Account, entry.item_id)
                if row is None:
                    raise WorkspaceError(404, 'Sentetik abone bulunamadı.')
                SubscriberWorkspace.authorize(row, user, True)
                require_workspace_account(user, entry.expected_router_id, row.access_type, True)
            receipts = [self.prior(session, entry, actor, user, group_id) for entry in entries]
            if all(receipts):
                return receipts
            if any(receipts):
                raise WorkspaceError(409, 'Bu işlem grubunun eski sonuçları eksik. İşlem geçmişini ve güncel aboneleri kontrol edin.')

            results = {}
            for entry in sorted(entries, key=lambda entry: (entry.expected_router_id, entry.item_id)):
                try:
                    results[entry.request_id] = self.change(entry, actor, user, group_id, transaction=session)
                except WorkspaceError as failure:
                    if failure.status == 503:
                        raise
                    results[entry.request_id] = self.failed(entry, actor, failure, user, group_id, transaction=session)
            return [results[entry.request_id] for entry in entries]

    @boundary
    def change(self,command,actor,user=None,group_id=None,*,transaction=None):
        context = self.sessions.begin() if transaction is None else transaction.begin_nested()
        with context as session_or_savepoint:
            session = session_or_savepoint if transaction is None else transaction
            if transaction is None:
                self.check(session)
                lock_operation_request(session, command.request_id)
            if user is not None:
                row=session.get(Account,command.item_id)
                if not row:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
                SubscriberWorkspace.authorize(row,user,True)
                require_workspace_account(user,command.expected_router_id,row.access_type,True)
                if command.operation=='ROUTER':
                    from app.core.security import current_admin
                    current_admin(user)
            if user is None:
                prior=self.prior(session,command,actor,user=user,group_id=group_id)
                if prior:return prior
            parents={command.expected_router_id}
            if command.operation=='ROUTER':
                try:
                    value=command.value or ''
                    if not value.startswith('demo-managed-router-'):raise ValueError()
                    UUID(value.removeprefix('demo-managed-router-'))
                except ValueError:raise WorkspaceError(422,'Yalnız kalıcı sentetik router ID seçin.') from None
                parents.add(value)
            locked_routers={id:SubscriberWorkspace.parent(session,id) for id in sorted(parents)}
            row=session.get(Account,command.item_id,with_for_update=True,populate_existing=True)
            if not row:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
            SubscriberWorkspace.authorize(row,user,True)
            prior=self.prior(session,command,actor,user=user,group_id=group_id)
            if prior:return prior
            if row.router_id!=command.expected_router_id or row.source!=command.expected_source or row.fields.get('source')!=row.source or row.fields.get('router_id')!=row.router_id:raise WorkspaceError(409,'Abone, router veya kaynak değişti. Güncel kaydı yeniden seçin.')
            if row.revision != command.expected_revision:
                raise WorkspaceError(409, 'Abone revizyonu önizlemeden sonra değişti. Güncel kaydı açıp yeni önizleme oluşturun.')
            if command.operation=='ROUTER' and command.value!=row.router_id:
                require_active_router(locked_routers[command.value])
            if command.operation=='STATUS' and command.value in ('ACTIVE','PAUSED'):
                current=row.fields.get('status')
                if command.expected_status is not None and current!=command.expected_status:
                    raise WorkspaceError(409,'Hesap durumu önizlemeden sonra değişti. Güncel kaydı yeniden seçin.')
                if current == command.value:
                    receipt = dict(item_id=row.id,request_id=str(command.request_id),success=False,recorded=False,skipped=True,
                                operation='STATUS',actor_id=actor,source=row.source,router_id=row.router_id,previous_router_id=row.router_id,
                                previous={'status':current},values={'status':current},occurred_at=datetime.now(timezone.utc).isoformat(),
                                revision=row.revision,error=None,**execution_metadata(group_id))
                    self.store_receipt(session, Skip, command, actor, {'status': {'previous': current, 'new': current}}, receipt, row.source)
                    return receipt
            field={'EDIT':'customer_name','PLAN':'plan','STATUS':'status','EXPIRE':'expires_on','EXTEND':'expires_on','ROUTER':'router_id'}[command.operation]
            value=command.value
            if command.operation in ('EDIT','PLAN'):
                value=(value or '').strip();limit=160 if command.operation=='EDIT' else 120
                if not (2 if command.operation=='EDIT' else 1)<=len(value)<=limit or not value.isprintable():raise WorkspaceError(422,'Ad veya paket/profil alanı geçersiz.')
            elif command.operation=='STATUS':
                if value not in ('ACTIVE','PAUSED'):raise WorkspaceError(422,'Hesap durumu Aktif veya Pasif olmalı.')
            elif command.operation=='EXPIRE' and value is not None:
                try:
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value) or date.fromisoformat(value).isoformat()!=value:raise ValueError()
                except ValueError:raise WorkspaceError(422,'Bitiş tarihi YYYY-MM-DD biçiminde olmalı.') from None
            elif command.operation=='EXTEND':
                old=row.fields.get('expires_on');today=datetime.now(ZoneInfo('Europe/Istanbul')).date()
                if not old or old!=command.expected_expires_on or command.days is None:raise WorkspaceError(409,'Bitiş tarihi bilinmiyor/değişti veya uzatma süresi eksik.')
                try:
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',old):raise ValueError()
                    expected=(max(date.fromisoformat(old),today)+timedelta(days=command.days)).isoformat()
                except (ValueError,OverflowError):raise WorkspaceError(422,'Kayıtlı tarih veya uzatma aralığı geçersiz.') from None
                if value!=expected:raise WorkspaceError(409,'Türkiye gününe göre uzatma önizlemesi değişti; yeniden inceleyin.')
            if field=='expires_on' and value and row.fields.get('started_on') and value<row.fields['started_on']:raise WorkspaceError(422,'Bitiş tarihi başlangıçtan önce olamaz.')
            package_values={}
            if field=='plan':
                if command.package_id:
                    from app.services.packages import binding
                    package_values=binding(session,command.package_id,command.package_revision)
                    if value!=package_values['plan']:raise WorkspaceError(409,'Seçilen paket önizlemeyle uyuşmuyor; yeniden seçip önizleyin.')
                    value=package_values['plan']
                else:package_values=dict(package_id=None,package_revision=None,package_snapshot=None)
            old=row.fields.get(field)
            if old==value and all(row.fields.get(key)==val for key,val in package_values.items()):raise WorkspaceError(422,'Yeni değer mevcut değerden farklı olmalı.')
            before=row.fields
            previous_router=row.router_id;row.fields={**row.fields,**package_values,field:value}
            if field=='router_id':row.router_id=value
            row.revision+=1;stamp=datetime.now(timezone.utc).isoformat()
            previous={field:old};values={field:value}
            if field in ('plan','expires_on'):
                previous.update({key:before.get(key) for key in ('plan','expires_on')})
                values.update({key:row.fields.get(key) for key in ('plan','expires_on')})
            if field=='plan':
                for key in ('package_id','package_revision'):
                    previous[key]=None if before.get(key) is None else str(before[key])
                    values[key]=None if row.fields.get(key) is None else str(row.fields[key])
            receipt=dict(item_id=row.id,request_id=str(command.request_id),success=True,recorded=True,operation=command.operation,actor_id=actor,router_id=row.router_id,previous_router_id=previous_router,previous=previous,values=values,occurred_at=stamp,revision=row.revision,error=None,**execution_metadata(group_id))
            changes={key:{'previous':previous[key],'new':values[key]} for key in values}
            if field=='plan':changes['_package_snapshot']={'previous':before.get('package_snapshot'),'new':row.fields.get('package_snapshot')}
            self.audit(session, command, actor, changes, receipt, row.source)
            return receipt
    def audit(self, session, command, actor, changes, receipt, source):
        self.store_receipt(session, Event, command, actor, changes, receipt, source)

    @staticmethod
    def store_receipt(session, model, command, actor, changes, receipt, source):
        receipt.setdefault('source', source)
        receipt.setdefault('skipped', False)
        session.add(model(id=str(command.request_id),subscriber_id=command.item_id,actor_id=actor,revision=receipt['revision'],operation=receipt['operation'],occurred_at=receipt['occurred_at'],changes={**changes,'_source':source,'_management':{'fingerprint':fingerprint(command,actor),'receipt':receipt}}))
    @boundary
    def failed(self,command,actor,error,user=None,group_id=None,*,transaction=None):
        context = self.sessions.begin() if transaction is None else transaction.begin_nested()
        with context as session_or_savepoint:
            session = session_or_savepoint if transaction is None else transaction
            if transaction is None:
                self.check(session)
                lock_operation_request(session, command.request_id)
            if user is None:
                prior=self.prior(session,command,actor,user=user,group_id=group_id)
                if prior:return prior
            row=session.get(Account,command.item_id,with_for_update=True)
            if user is not None:
                if row is None:raise WorkspaceError(404,'Sentetik abone bulunamadı.')
                SubscriberWorkspace.authorize(row,user,True)
            prior=self.prior(session,command,actor,user=user,group_id=group_id)
            if prior:return prior
            receipt=dict(item_id=command.item_id,request_id=str(command.request_id),success=False,recorded=True,operation=command.operation,actor_id=actor,router_id=row.router_id if row else None,previous_router_id=row.router_id if row else None,previous={},values={},occurred_at=datetime.now(timezone.utc).isoformat(),revision=row.revision if row else 0,error=error.detail,**execution_metadata(group_id))
            self.audit(session, command, actor, {}, receipt, row.source if row and row.fields.get('source')==row.source else None)
            return receipt
    @boundary
    def lookup(self,command,actor,user=None,group_id=None):
        with self.sessions() as session:
            self.check(session)
            if user is not None:
                row=session.get(Account,command.item_id)
                if row is None:return None
                SubscriberWorkspace.authorize(row,user,True)
            return self.prior(session,command,actor,user=user,group_id=group_id)
    def execute(self,command,actor,user=None,group_id=None):
        try:return self.change(command,actor,user=user,group_id=group_id)
        except WorkspaceError as failure:
            if failure.status!=503:
                try:return self.failed(command,actor,failure,user=user,group_id=group_id)
                except WorkspaceError as recording_error:
                    if recording_error.status==409:
                        try:
                            prior=self.lookup(command,actor,user=user,group_id=group_id)
                            if prior:return prior
                        except WorkspaceError:pass
            # Persistence is unavailable or request ID conflicts: never claim a saved receipt.
            return dict(item_id=command.item_id,request_id=str(command.request_id),success=False,recorded=False,operation=command.operation,actor_id=actor,router_id=None,previous_router_id=None,previous={},values={},occurred_at=datetime.now(timezone.utc).isoformat(),revision=0,error=failure.detail,**execution_metadata(group_id))
    @boundary
    def request_result(self,request_id,actor,user=None):
        with self.sessions() as session:
            if session.bind.dialect.name=='postgresql':
                session.connection(execution_options={'isolation_level':'REPEATABLE READ','postgresql_readonly':True})
            self.check(session)
            result={'request_id':str(request_id),'status':'UNKNOWN','response':None}
            prior=session.get(Event,str(request_id))
            if prior is None or '_management' not in prior.changes:
                skipped = session.get(Skip, str(request_id))
                if skipped is None or skipped.actor_id != actor:
                    return result
                account = session.get(Account, skipped.subscriber_id)
                if account is None:
                    return result
                SubscriberWorkspace.authorize(account, user)
                receipt = event_receipt(skipped, skipped=True)
                if user is not None:
                    from app.core.authorization import require_workspace_router
                    require_workspace_router(user, receipt['router_id'])
                return {**result, 'status': 'SKIPPED', 'response': receipt}
            if prior.actor_id!=actor:return result
            if prior.operation == 'UNDO':
                undo = event_receipt(prior)
                self.undo_entry(session, undo['source_request_id'], workspace_scope(user) if user is not None else None)
            receipt=prior.changes.get('_management',{}).get('receipt')
            if not receipt or receipt.get('recorded') is not True or receipt.get('request_id')!=str(request_id) or receipt.get('item_id')!=prior.subscriber_id or receipt.get('actor_id')!=actor:return result
            account=session.get(Account,prior.subscriber_id)
            if user is not None and account is not None:
                SubscriberWorkspace.authorize(account,user)
                from app.core.authorization import require_workspace_router
                for key in ('router_id','previous_router_id'):
                    if receipt.get(key):require_workspace_router(user,receipt[key])
            if (receipt.get('revision')!=prior.revision or receipt.get('operation')!=prior.operation
                    or receipt.get('occurred_at')!=prior.occurred_at or type(receipt.get('success')) is not bool
                    or receipt.get('values')!=public_changes(prior.changes,'new')
                    or receipt.get('previous')!=public_changes(prior.changes,'previous')):return result
            if prior.operation=='ROUTER' and receipt['success']:
                if receipt.get('router_id')!=receipt['values'].get('router_id') or receipt.get('previous_router_id')!=receipt['previous'].get('router_id'):return result
            elif receipt.get('router_id')!=receipt.get('previous_router_id'):return result
            evidence=request_audit(prior,account,receipt.get('router_id'),account.source if account else None,receipt['success'])
            if not evidence:return result
            if account.revision==prior.revision and receipt['success'] and any((None if account.fields.get(key) is None else str(account.fields[key]))!=value for key,value in receipt['values'].items()):return result
            return {**result,'status':'SUCCESS' if receipt['success'] else 'FAILED','response':receipt,'audit':evidence}

    @staticmethod
    def undo_read_snapshot(session):
        if session.get_bind().dialect.name == 'postgresql':
            session.connection(execution_options={'isolation_level':'REPEATABLE READ','postgresql_readonly':True})

    @staticmethod
    def undo_query(model, scope):
        query = select(model, Account).join(Account, Account.id == model.subscriber_id)
        if scope is not None:
            query = query.where(Account.router_id.in_(scope), *event_scope(scope, model))
        return query

    def undo_entry(self, session, request_id, scope):
        entry = session.execute(self.undo_query(Event, scope).where(Event.id == str(request_id))).one_or_none()
        if entry is None or '_management' not in entry[0].changes:
            skipped = session.execute(self.undo_query(Skip, scope).where(Skip.id == str(request_id))).one_or_none()
            entry = skipped or entry
        if entry is None:
            raise WorkspaceError(404, 'İşlem kaydı bulunamadı.')
        return entry

    @staticmethod
    def successful_undos(session, events):
        if not events:
            return {}
        source_id = Event.changes['_undo']['source_request_id'].as_string()
        success = Event.changes['_management']['receipt']['success'].as_boolean()
        statement = select(Event).where(Event.operation == 'UNDO', source_id.in_([event.id for event in events]),
                                        success.is_(True)).order_by(Event.occurred_at, Event.id)
        sources = {(event.id,event.subscriber_id) for event in events}
        matched = {}
        for event in session.scalars(statement):
            receipt = event_receipt(event)
            key = (receipt['source_request_id'], event.subscriber_id)
            if key in sources:
                matched.setdefault(key, event.id)
        return matched

    @staticmethod
    def group_member_ids(session, group_id):
        return [id for model in (Event, Skip) for id in session.scalars(
            select(model.id).where(model.changes['_management']['receipt']['group_id'].as_string() == group_id).limit(101))]

    @boundary
    def undo_preview(self, request_id, user):
        scope = workspace_scope(user)
        with self.sessions() as session:
            self.undo_read_snapshot(session)
            self.check(session)
            event, account = self.undo_entry(session, request_id, scope)
            preview = self.evaluate_undo(session, event, account, user, self.successful_undos(session, [event]))
            if preview['source_group_id']:
                preview['can_execute'] = False
            return preview

    @boundary
    def undo_group_preview(self, group_id, user):
        scope = workspace_scope(user)
        with self.sessions() as session:
            self.undo_read_snapshot(session)
            self.check(session)
            entries = []
            for model in (Event, Skip):
                group = model.changes['_management']['receipt']['group_id'].as_string()
                query = self.undo_query(model, scope).where(group == str(group_id)).limit(101)
                entries.extend(session.execute(query).all())
            if not entries:
                raise WorkspaceError(404, 'İşlem grubu bulunamadı.')
            if len(entries) > 100:
                raise WorkspaceError(409, 'İşlem grubu kayıt sınırını aşıyor.')
            undone = self.successful_undos(session, [event for event, _ in entries])
            items = [self.evaluate_undo(session, event, account, user, undone)
                     for event, account in sorted(entries, key=lambda entry: (entry[0].occurred_at, entry[0].id))]
            members = self.group_member_ids(session, str(group_id))
            complete = len(entries) == len(members) and group_id_for_requests(members, entries[0][0].actor_id) == str(group_id)
            can_execute = complete and all(item['can_execute'] for item in items)
            return dict(group_id=group_id, items=items, can_execute=can_execute,
                        reason=None if can_execute else 'Grubun tamamı erişilebilir ve geri alınabilir olmalıdır.')

    @staticmethod
    def evaluate_undo(session, event, account, user, undone, *, router_kind=None, skipped=False):
        preview = dict(request_id=event.id, item_id=account.id, subscriber_name=account.fields.get('customer_name'),
                       operation=event.operation, actor_id=event.actor_id, occurred_at=event.occurred_at,
                       audit_revision=event.revision, current_revision=account.revision,
                       changes=[], status='INELIGIBLE', can_execute=False, source_group_id=None)
        skipped = skipped or isinstance(event, Skip)
        if not event.changes.get('_management', {}).get('receipt'):
            return {**preview, 'reason': 'Bu geçmiş kaydı geri alma için yeterli işlem kanıtı içermiyor.'}
        try:
            receipt = event_receipt(event, skipped=skipped)
        except WorkspaceError:
            return {**preview, 'reason': 'Geçmiş işlem kanıtı doğrulanamadı.'}
        try:
            preview['source_group_id'] = undo_source_group(receipt)
        except WorkspaceError as error:
            return {**preview, 'reason': error.detail}
        if skipped:
            return {**preview, 'reason': 'İşlem atlandı. Abonelik değerleri değişmedi.'}
        if not receipt['success']:
            return {**preview, 'reason': 'İşlem reddedildi. Geri alınacak bir değişiklik yok.'}

        previous, applied = receipt['previous'], receipt['values']
        for field in sorted(previous.keys() & applied.keys()):
            if (field in account.fields and {'previous', 'new'} <= event.changes[field].keys()
                    and previous[field] != applied[field]):
                value = account.fields[field]
                preview['changes'].append(dict(field=field, previous=previous[field], applied=applied[field],
                                               current=None if value is None else str(value)))
        undo_id = undone.get((event.id, account.id))
        if undo_id:
            return {**preview, 'status': 'UNDONE', 'undo_request_id': undo_id, 'reason': 'Bu işlemin başarılı geri alma kaydı var.'}
        if user is not None and not workspace_can_manage(user, account.router_id, account.access_type):
            return {**preview, 'reason': 'Bu aboneliği yönetme yetkiniz bulunmuyor.'}
        field = UNDO_PREVIEW_FIELDS.get(event.operation)
        if field is None:
            return {**preview, 'reason': 'Bu işlem türü için güvenli geri alma uygunluğu değerlendirilmiyor.'}
        audit_change = event.changes.get(field)
        if (not isinstance(audit_change, dict) or not {'previous', 'new'} <= audit_change.keys()
                or field not in account.fields or previous[field] == applied[field] or event.revision < 1):
            return {**preview, 'reason': 'Değişen alanın önceki, işlenen veya güncel değeri doğrulanamadı.'}

        if router_kind is None:
            router = session.get(RouterWorkspaceRecord, account.router_id)
            router_kind = router.kind if router else None
        source = event_source(event)
        if router_kind != 'DEMO_ROUTER' or source is None:
            return {**preview, 'reason': 'Sentetik router veya kayıtlı yetkili kaynak doğrulanamadı.'}
        if (account.router_id != receipt['router_id'] or account.fields.get('router_id') != account.router_id
                or source != account.source or account.fields.get('source') != account.source
                or account.fields.get('access_type') != account.access_type):
            return {**preview, 'status': 'CONFLICT', 'reason': 'Aboneliğin routerı, erişim türü veya yetkili kaynağı değişti.'}
        if account.revision != event.revision:
            return {**preview, 'status': 'CONFLICT', 'reason': 'İşlemden sonra abonelik revizyonu değişti.'}
        current = account.fields[field]
        if (None if current is None else str(current)) != applied[field]:
            return {**preview, 'status': 'CONFLICT', 'reason': 'Güncel değer, işlemde kaydedilen değerle eşleşmiyor.'}
        if not valid_previous_value(field, previous[field], account):
            return {**preview, 'reason': 'Önceki değer güncel abonelik kurallarına uymuyor.'}
        return {**preview, 'status': 'ELIGIBLE', 'can_execute': local_undo_enabled(), 'reason': 'Güncel revizyon ve değer geçmiş kayıtla eşleşiyor. Önceki değer önizlenebilir.'}

    @boundary
    def execute_undo(self, entries, user):
        if not local_undo_enabled():
            raise WorkspaceError(403, 'Geri alma yalnız yerel izole kabul ortamında kullanılabilir.')
        actor = user['id']
        scope = workspace_scope(user)
        group_id = bulk_group_id(entries, actor)
        with self.sessions.begin() as session:
            self.check(session)
            if session.get_bind().dialect.name == 'sqlite':
                session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            for entry in sorted(entries, key=lambda entry: entry.request_id):
                lock_operation_request(session, entry.request_id)

            accounts = {}
            for entry in sorted(entries, key=lambda entry: entry.item_id):
                account = session.get(Account, entry.item_id, with_for_update=True)
                if account is None:
                    raise WorkspaceError(404, 'Sentetik abone bulunamadı.')
                SubscriberWorkspace.authorize(account, user, True)
                accounts[entry.item_id] = account

            sources = [self.undo_entry(session, entry.source_request_id, scope)[0] for entry in entries]
            for entry, source in zip(entries, sources, strict=True):
                if source.subscriber_id != entry.item_id:
                    raise WorkspaceError(409, 'Kaynak işlem bu aboneliğe ait değil.')

            receipts = [self.prior(session, entry, actor, user, group_id) for entry in entries]
            if all(receipts):
                return receipts
            if any(receipts):
                raise WorkspaceError(409, 'Geri alma grubunun kayıtlı sonuçları eksik.')

            source_ids = {source.id for source in sources}
            source_groups = {undo_source_group(source.changes.get('_management', {}).get('receipt', {})) for source in sources}
            if len(source_groups) != 1 or (len(entries) > 1 and None in source_groups):
                raise WorkspaceError(409, 'Toplu geri alma tek bir kaynak işlem grubu gerektirir.')
            source_group = next(iter(source_groups))
            if source_group is not None:
                members = self.group_member_ids(session, source_group)
                if (len(members) != len(source_ids) or set(members) != source_ids
                        or group_id_for_requests(members, sources[0].actor_id) != source_group):
                    raise WorkspaceError(409, 'Kaynak grubun tamamı doğrulanamadı. Geri alma uygulanmadı.')
            undone = self.successful_undos(session, sources)

            errors = []
            for entry, source in zip(entries, sources, strict=True):
                preview = self.evaluate_undo(session, source, accounts[entry.item_id], user, undone)
                expected = dict(field=entry.field, previous=entry.previous, applied=entry.applied, current=entry.applied)
                if preview['status'] != 'ELIGIBLE':
                    errors.append(preview['reason'])
                elif (preview['current_revision'] != entry.expected_revision or preview['changes'] != [expected]
                      or preview['source_group_id'] != (str(entry.source_group_id) if entry.source_group_id else None)):
                    errors.append('Onaylanan geri alma önizlemesi değişti. Yeni önizleme oluşturun.')
                else:
                    errors.append(None)

            rejected = any(errors)
            results = []
            for entry, source, error in zip(entries, sources, errors, strict=True):
                account = accounts[entry.item_id]
                source_receipt = source.changes.get('_management', {}).get('receipt', {})
                origin = dict(source_request_id=source.id, source_group_id=source_group)
                origin_router = source.changes.get('_router_id') or source_receipt.get('router_id')
                before, after = {}, {}
                if not rejected:
                    before, after = {entry.field: entry.applied}, {entry.field: entry.previous}
                    account.fields = {**account.fields, **after}
                    account.revision += 1
                elif error is None:
                    error = 'Gruptaki başka bir kayıt reddedildi. Toplu geri alma uygulanmadı.'
                receipt = dict(item_id=account.id, request_id=str(entry.request_id), success=not rejected,
                               recorded=True, operation='UNDO', actor_id=actor, router_id=account.router_id,
                               previous_router_id=account.router_id, previous=before, values=after,
                               occurred_at=datetime.now(timezone.utc).isoformat(), revision=account.revision,
                               error=error, **execution_metadata(group_id), **origin)
                changes = {key: {'previous': before[key], 'new': value} for key, value in after.items()}
                self.audit(session, entry, actor, {**changes, '_undo': {**origin, 'source_router_id': origin_router}},
                           receipt, account.source)
                results.append(receipt)
            return results

    @boundary
    def history(self,item_id='',operation='ALL',result='ALL',page=1,page_size=25,*,start=None,until=None,
                router_id='',actor_id='',query='',user=None,daily=False,execution_type='ALL',group_filter=None,include_skipped=False,request_filter=None,undo_status='ALL'):
        with self.sessions() as session:
            self.undo_read_snapshot(session)
            self.check(session)
            event = Event
            skipped = literal(False)
            if daily or include_skipped:
                events = select(Event, literal(False).label('skipped'))
                if daily:
                    events = events.where(Event.operation.in_(DAILY_REPORT_OPERATIONS))
                ledger = union_all(
                    events,
                    select(Skip, literal(True).label('skipped')),
                ).subquery()
                event = aliased(Event, ledger)
                skipped = ledger.c.skipped

            scoped = []
            if user is not None:
                ids = workspace_scope(user)
                if ids is not None:
                    scoped.extend([Account.router_id.in_(ids), *event_scope(ids, event)])

            receipt = event.changes['_management']['receipt']
            group_id = receipt['group_id'].as_string()
            mode = receipt['execution_type'].as_string()
            outcome = case(
                (skipped, 'SKIPPED'),
                (event.operation.in_(('CREATE','UPDATE','RENEWAL')), 'SUCCESS'),
                (receipt['success'].as_boolean().is_(True), 'SUCCESS'),
                (receipt['success'].as_boolean().is_(False), 'FAILED'),
            )
            clauses = list(scoped)
            if start:clauses.append(event.occurred_at >= start)
            if until:clauses.append(event.occurred_at < until)
            if item_id:clauses.append(event.subscriber_id == item_id)
            if router_id:clauses.append(Account.router_id == router_id)
            if actor_id:clauses.append(event.actor_id == actor_id)
            if operation != 'ALL':clauses.append(event.operation == operation)
            if execution_type == 'UNKNOWN':clauses.append(mode.is_(None))
            elif execution_type != 'ALL':clauses.append(mode == execution_type)
            if group_filter:clauses.append(group_id == group_filter)
            if request_filter:clauses.append(event.id == request_filter)
            if query:
                pattern = '%' + query + '%'
                clauses.append((event.id.ilike(pattern)) | (event.actor_id.ilike(pattern)) |
                               (event.subscriber_id.ilike(pattern)) | (Account.fields['customer_name'].as_string().ilike(pattern)) |
                               (Account.fields['username'].as_string().ilike(pattern)))

            joined = select(event).join(Account, Account.id == event.subscriber_id)
            counts, groups = None, []
            tallies = None
            if daily:
                summary = joined.with_only_columns(outcome, func.count(), maintain_column_froms=True)
                tallies = dict(session.execute(summary.where(*clauses).group_by(outcome)).all())
                counts = self.outcome_counts(tallies)

            if result != 'ALL':
                clauses.append(outcome == result)
            filtered = joined.where(*clauses)
            statement = filtered.add_columns(Account.fields['customer_name'].as_string(),
                                             Account.fields['username'].as_string(), skipped)
            if include_skipped:
                statement = statement.outerjoin(RouterWorkspaceRecord, Account.router_id == RouterWorkspaceRecord.id)
                statement = statement.add_columns(Account, func.coalesce(RouterWorkspaceRecord.kind, ''))
            statement = statement.order_by(event.occurred_at.desc(), event.id)
            offset = (page-1)*page_size
            items = []
            if undo_status == 'ALL':
                if tallies is not None:
                    total = sum(tallies.values()) if result == 'ALL' else tallies.get(result, 0)
                else:
                    total = session.scalar(filtered.with_only_columns(func.count(), maintain_column_froms=True))
                batches = [session.execute(statement.offset(offset).limit(page_size)).all()] if offset < total else []
            else:
                total = 0
                batches = session.execute(statement.execution_options(yield_per=100)).partitions()
            for batch in batches:
                undone = self.successful_undos(session, [row[0] for row in batch]) if include_skipped else {}
                for record,name,username,is_skipped,*context in batch:
                    item = {**event_receipt(record, skipped=is_skipped), 'source':event_source(record)}
                    if daily or include_skipped:
                        item.update(subscriber_name=name, subscriber_username=username)
                    if include_skipped:
                        account, router_kind = context
                        preview = self.evaluate_undo(session, record, account, user, undone,
                                                     router_kind=router_kind, skipped=is_skipped)
                        item.update(undo_status=preview['status'], undo_request_id=preview.get('undo_request_id'))
                    if undo_status != 'ALL':
                        if item.get('undo_status') != undo_status:
                            continue
                        total += 1
                        if not offset < total <= offset+page_size:
                            continue
                    items.append(item)

            if daily:
                group_ids = sorted({item['group_id'] for item in items if item.get('group_id')})
                if group_ids:
                    summary = joined.with_only_columns(group_id, outcome, func.count(), maintain_column_froms=True)
                    grouped = {id: {} for id in group_ids}
                    for id, status, count in session.execute(summary.where(*scoped, group_id.in_(group_ids)).group_by(group_id, outcome)):
                        grouped[id][status] = count
                    groups = [dict(group_id=id, total=sum(tallies.values()), **self.outcome_counts(tallies))
                              for id,tallies in grouped.items()]
            return dict(items=items,total=total,page=page,page_size=page_size,is_demo=True,
                        **(dict(counts=counts,groups=groups) if daily else {}))

    @staticmethod
    def outcome_counts(tallies):
        return dict(success=tallies.get('SUCCESS',0),failed=tallies.get('FAILED',0),skipped=tallies.get('SKIPPED',0))


operations=SubscriberOperationsService()
