# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import logging

from rest_framework.permissions import BasePermission

logger = logging.getLogger('apps')


class IsTpServerUser(BasePermission):
    #request权限验证

    def has_permission(self, request, view):
        return request.verify
    #return True