"""Pure projection of the already authenticated V2 session. No identity/grant creation.

is_demo marks the current V2 environment for ALL accounts; it is not a bootstrap test.
A display name or translated role name never establishes pilot eligibility.
"""


def pilot_identity(user):
    if not isinstance(user,dict):return {'state':'UNVERIFIED','candidate':None}
    candidate=None
    id=user.get('id')
    revision=user.get('revision')
    if (user.get('is_demo') is not True or not isinstance(id,str) or not id.strip()
            or len(id)>80 or id!=id.strip() or any(ord(c)<32 or ord(c)==127 for c in id)):
        state='UNVERIFIED'
    elif id=='demo-user':state='BOOTSTRAP_DEMO'
    elif user.get('active') is False:state='INACTIVE'
    elif (user.get('active') is not True or type(revision) is not int or revision<0
            or user.get('role_code') not in ('ADMIN','VIEWER') or type(user.get('can_manage_users')) is not bool):
        state='UNVERIFIED'
    elif user['role_code']!='ADMIN':state='NOT_ADMIN'
    elif not user['can_manage_users']:state='INSUFFICIENT_SCOPE'
    else:
        state='ELIGIBLE'
        candidate={'id':id,'revision':revision,'source':'V2_AUTHENTICATED_SESSION'}
    return {'state':state,'candidate':candidate}
