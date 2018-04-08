# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime

from django.db import models
from audit_log.models.managers import AuditLog
from django.utils.translation import ugettext_lazy as _

class CreateDateTimeModel(models.Model):
    #包含created_at字段的抽象类
    created_at = models.DateTimeField('创建时间’, auto_now_add=True',
                                      help_text=_('创建时间'))

    class Meta:
        abstract = True

class UpdateDateTimeModel(models.Model):
    #包含updated_at字段的抽象类
    updated_at = models.DateTimeField('更新时间’, auto_now=True',
                                      help_text=_('更新时间'))

    class Meta:
        abstract = True

class DeleteDateTimeModel(models.Model):
    #包含deleted_at抽象类
    deleted_at = models.DateTimeField('删除时间', null=True, blank=True,
                                      help_text=_('删除时间'))

    class Meta:
        abstract = True

    def update_delete(self):                        #对删除的状态进行判断
        #更新为已删除
        if self.deleted_at:
            #已删除
            re = 2
        else:
            #更新为删除
            self.deleted_at = datetime.now()
            self.save(update_fields=['deleted_at'])
            re = 1
        return re


class CreateUpdateDateTimeModel(CreateDateTimeModel,UpdateDateTimeModel):
    """包含created_at与updated_at两个字段"""

    class Meta:
        abstract = True


class CreateUpdateDeleteDateTimeModel(CreateUpdateDateTimeModel,
                                      DeleteDateTimeModel):
    """包含created_at updated_at与deleted_at三个字段的抽象类"""

    class Meta:
        abstract = True


class UpdateDeleteDateTimeModel(UpdateDateTimeModel, DeleteDateTimeModel):
    """包含updated_at与deleted_at两个字段的抽象类"""

    class Meta:
        abstract = True


class DefaultManager(models.Manager):   #自定义默认管理器，并修改返回查询集  第一个声明的管理器就是默认管理器
    use_for_related_fields = True       #设置为True后Django会始终使用这个管理器，不会自动创建管理器

    def get_queryset(self):
        queryset = super(DefaultManager, self).get_queryset().filter(is_delete=False)    #此处是super()继承。 返回未删除的对象
        return queryset


class DeleteFieldModel(models.Model):
    is_delete = models.BooleanField('删除', default=False, editable=False)

    objects = DefaultManager()
    audit_log = AuditLog()

    def soft_delete(self):                        #方法命名不清晰
        self.is_delete = True
        self.updated_at = datetime.now()
        self.save(update_fields=['is_delete', 'update_at'], force_update=True)

    class Meta:
            abstract = True