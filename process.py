from qgis.core import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

# initialize Qt resources from file resources.py
from . import resources
from .form import message

class transmat:
  def __init__(self, iface):
    # save reference to the QGIS interface
    self.iface = iface
    self.msg=message()

  def initGui(self):
    # create action that will start plugin configuration
    self.action = QAction(QIcon(":/plugins/custom/icon.png"), "Transmat", self.iface.mainWindow())
    self.action.triggered.connect(self.run)

    # add toolbar button and menu item
    self.iface.addToolBarIcon(self.action)
    self.iface.addPluginToMenu("&Home made", self.action)

  def unload(self):
    # remove the plugin menu item and icon
    self.iface.removePluginMenu("&Home made", self.action)
    self.iface.removeToolBarIcon(self.action)

  def run(self):
    # create and show a configuration dialog or something similar
    #print "TestPlugin: run called!"
    self.msg.show()

