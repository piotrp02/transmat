# -*- coding: utf-8 -*-
def classFactory(iface):
    from .process import transmat
    return transmat(iface)
