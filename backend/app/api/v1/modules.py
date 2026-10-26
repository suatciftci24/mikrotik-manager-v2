from fastapi import APIRouter, Depends
from app.core.security import current_demo_user

router = APIRouter(prefix='/modules', tags=['modules'])
MODULES = [
    {'key': 'system', 'name': 'Sistem ve Kullanıcı', 'status': 'PHASE_1_DEMO'},
    {'key': 'routers', 'name': 'Router Yönetimi', 'status': 'PHASE_1_DEMO'},
    {'key': 'subscribers', 'name': 'Abone Yönetimi', 'status': 'PHASE_1_DEMO'},
    {'key': 'radius', 'name': 'RADIUS Entegrasyonu', 'status': 'SCAFFOLD'},
    {'key': 'operations', 'name': 'Operasyon Merkezi', 'status': 'SCAFFOLD'},
    {'key': 'mikajani', 'name': 'MikAjanı', 'status': 'SCAFFOLD'},
]


@router.get('')
def module_status(_user: dict = Depends(current_demo_user)):
    return {'items': MODULES, 'is_demo': True}
