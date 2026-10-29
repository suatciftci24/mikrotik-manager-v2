"""Explicit V2 ORM model registry."""
from app.models.access import Permission, Role, role_permissions
from app.models.identity import PanelUser
from app.models.network import Router
from app.models.operations import AuditLog, SubscriberEvent
from app.models.subscriptions import AuthoritativeSource, Customer, SubscriberAccount, SubscriptionPlan

__all__ = ['AuditLog', 'AuthoritativeSource', 'Customer', 'PanelUser', 'Permission',
           'Role', 'Router', 'SubscriberAccount', 'SubscriberEvent', 'SubscriptionPlan', 'role_permissions']

from app.models.router_registry import RegisteredRouter, RouterVerification, RouterRegistryAudit
__all__ += ['RegisteredRouter', 'RouterVerification', 'RouterRegistryAudit']
