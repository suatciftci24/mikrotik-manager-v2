"""Explicit typed JSON checkpoint codec; no pickle, dynamic import or provider data."""
from datetime import datetime
import json
from uuid import UUID
from app.integrations.aaa_contracts import ReadContract
from app.simulation import (aaa_atomic, aaa_worker, aaa_decision, aaa_followup, aaa_execution,
    aaa_executor, aaa_executor_decision, aaa_executor_policy, aaa_next_step,
    aaa_next_step_preparation, aaa_prepared_authorization)

MODULES = (aaa_atomic, aaa_worker, aaa_decision, aaa_followup, aaa_execution, aaa_executor,
           aaa_executor_decision, aaa_executor_policy, aaa_next_step, aaa_next_step_preparation,
           aaa_prepared_authorization)
MODELS = {cls.__module__ + '.' + cls.__name__: cls for module in MODULES for cls in vars(module).values()
          if isinstance(cls, type) and issubclass(cls, ReadContract) and cls.__module__ == module.__name__}


def encode(value):
    if isinstance(value, ReadContract):
        name = type(value).__module__ + '.' + type(value).__name__
        if name not in MODELS:
            raise ValueError('CHECKPOINT_MODEL_REJECTED')
        # Revalidate even caller-mutated model_copy instances.
        value = MODELS[name].model_validate_json(value.model_dump_json())
        return {'t': 'model', 'name': name, 'v': value.model_dump(mode='json')}
    if isinstance(value, UUID):
        return {'t': 'uuid', 'v': str(value)}
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError('AWARE_CHECKPOINT_TIME_REQUIRED')
        return {'t': 'datetime', 'v': value.isoformat()}
    if type(value) is dict:
        return {'t': 'dict', 'v': [[encode(k), encode(v)] for k, v in value.items()]}
    if type(value) in (tuple, list, set):
        values = [encode(v) for v in value]
        if type(value) is set:
            values.sort(key=lambda v: json.dumps(v, sort_keys=True))
        return {'t': type(value).__name__, 'v': values}
    if value is None or type(value) in (str, int, bool):
        return value
    raise ValueError('CHECKPOINT_VALUE_REJECTED')


def decode(value):
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is not dict or set(value) not in ({'t', 'v'}, {'t', 'name', 'v'}):
        raise ValueError('CHECKPOINT_ENCODING_REJECTED')
    kind, raw = value['t'], value['v']
    if kind == 'model' and value.get('name') in MODELS:
        return MODELS[value['name']].model_validate_json(json.dumps(raw))
    if kind == 'uuid':
        return UUID(raw)
    if kind == 'datetime':
        result = datetime.fromisoformat(raw)
        if result.utcoffset() is None:
            raise ValueError('AWARE_CHECKPOINT_TIME_REQUIRED')
        return result
    if kind == 'dict':
        result = {}
        for key, item in raw:
            key = decode(key)
            if key in result:
                raise ValueError('DUPLICATE_CHECKPOINT_KEY')
            result[key] = decode(item)
        return result
    if kind in ('tuple', 'list', 'set'):
        return {'tuple': tuple, 'list': list, 'set': set}[kind](decode(item) for item in raw)
    raise ValueError('CHECKPOINT_TYPE_REJECTED')
