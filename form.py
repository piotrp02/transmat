from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
import numpy as np

from .geospatial import renderer


class message(QDialog):
    def __init__(self):
        super().__init__()
        self.resize(800,800)
        self.setWindowTitle("Transmat")

        self.raster1_combo_label = QLabel("Raster 1")
        self.raster1_combo = QgsMapLayerComboBox()
        self.raster1_combo.setFilters(Qgis.LayerFilter.RasterLayer)

        self.raster2_combo_label = QLabel("Raster 2")
        self.raster2_combo = QgsMapLayerComboBox()
        self.raster2_combo.setFilters(Qgis.LayerFilter.RasterLayer)

        self.na_spin_label = QLabel("NA Value")
        self.na_spin = QSpinBox()
        self.na_spin.setMinimum(-9999)
        self.na_spin.setMaximum(9999)
        self.na_spin.setValue(0)

        self.percentage_checkbox = QCheckBox("Calculate percentages")

        # Button to generate matrix
        self.generate_btn = QPushButton("Generate Transition Matrix")

        # Matrix table
        self.transition_counts = np.array([])
        self.table_widget = QTableWidget()

        self.transition_mask_tip_label = QLabel()

        # Selection plot
        self.transition_mask = np.array([])
        self.pixmap_label = QLabel()
        width, height = 200, 200
        self.pixmap_white = QPixmap(width, height)
        self.pixmap_label.setFixedSize(width, height)
        self.pixmap_white.fill(Qt.white)
        self.pixmap_label.setPixmap(self.pixmap_white)

        self.close_button = QPushButton("&Close")
        self.save_matrix_button = QPushButton("&Save Transition Matrix")
        self.save_selection_button = QPushButton("&Save Transition Mask")
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.close_button)
        self.button_layout.addWidget(self.save_matrix_button)
        self.button_layout.addWidget(self.save_selection_button)

        # Add to your main layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.raster1_combo_label)
        mainLayout.addWidget(self.raster1_combo)
        mainLayout.addWidget(self.raster2_combo_label)
        mainLayout.addWidget(self.raster2_combo)
        mainLayout.addWidget(self.na_spin_label)
        mainLayout.addWidget(self.na_spin)
        mainLayout.addWidget(self.percentage_checkbox)
        mainLayout.addWidget(self.generate_btn)
        mainLayout.addWidget(self.table_widget)
        mainLayout.addWidget(self.transition_mask_tip_label, alignment=Qt.AlignCenter)
        mainLayout.addWidget(self.pixmap_label, alignment=Qt.AlignCenter)
        mainLayout.addLayout(self.button_layout)
        self.setLayout(mainLayout)

        # Actions
        self.generate_btn.clicked.connect(self.compute_transition_matrix)
        self.close_button.clicked.connect(self.close)
        self.save_matrix_button.clicked.connect(self.save_matrix)
        self.table_widget.cellClicked.connect(self.on_cell_clicked)
        self.save_selection_button.clicked.connect(self.save_transition_mask_as_tif)

    def compute_transition_matrix(self):
        raster1_layer = self.raster1_combo.currentLayer()
        raster2_layer = self.raster2_combo.currentLayer()
        null_value = self.na_spin.value()

        if not raster1_layer or not raster2_layer:
            QMessageBox.warning(self, "Missing Input", "Please select two raster layers.")
            return
        
        rast_check = renderer.check_rasters(self, raster1_layer, raster2_layer)
        if rast_check is not None:
            QMessageBox.warning(self, "Raster Layer Error" ,rast_check)
            return


        matrix = renderer.calculate_transmat(self, raster1_layer, raster2_layer, null_value)
        if self.percentage_checkbox.isChecked():
            matrix = (matrix / matrix.sum()) * 100
            matrix = np.round(matrix, 2)

        self.table_widget.clear()
        self.table_widget.setRowCount(self.n_classes)
        self.table_widget.setColumnCount(self.n_classes)
        self.table_widget.setHorizontalHeaderLabels([str(v) for v in self.unique_values])
        self.table_widget.setVerticalHeaderLabels([str(v) for v in self.unique_values])

        for i in range(self.n_classes):
            for j in range(self.n_classes):
                item = QTableWidgetItem(str(matrix[i, j]))
                item.setTextAlignment(Qt.AlignCenter)
                self.table_widget.setItem(i, j, item)
        
        self.pixmap_label.setPixmap(self.pixmap_white)
        self.transition_mask_tip_label.setText("Click on a cell to generate a transition mask.")
        self.transition_mask = np.array([])
    
    def save_matrix(self):
        if self.transition_counts.size == 0:
            QMessageBox.warning(self, "Error", "Transition matrix is empty.")
            return
        filename, _ = QFileDialog.getSaveFileName(
                parent=self,
                caption="Save Transition Matrix",
                filter="CSV files (*.csv);;All files (*)"
            )
        if not filename:
            return

        if not filename.lower().endswith(".csv"):
            filename += ".csv"
        try:
            np.savetxt(filename, self.transition_counts, delimiter=";", fmt='%d')
            QMessageBox.information(self, "Saved", f"Transition matrix saved to:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")

    def on_cell_clicked(self, row, column):
        self.transition_mask = renderer.get_selection(self, row, column)
        grayscale = np.where(self.transition_mask, 0, 255).astype(np.uint8)
        height, width = grayscale.shape
        bytes_per_line = width
        qimg = QImage(grayscale.data, width, height, bytes_per_line, QImage.Format_Grayscale8).copy()
        pixmap = QPixmap.fromImage(qimg)
        scaled_pixmap = pixmap.scaled(self.pixmap_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)        
        self.pixmap_label.setPixmap(scaled_pixmap)
        self.transition_mask_tip_label.setText("")

    def save_transition_mask_as_tif(self):
        if self.transition_mask.size == 0:
            QMessageBox.warning(self, "Error", "The transition mask is empty. Please select a cell from the transition matrix.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Save Image",
            filter="TIFF files (*.tif *.tiff)",
        )

        if not filename:
            return
        
        if filename and not filename.lower().endswith(('.tif', '.tiff')):
            filename += ".tif"

        try:
            bufor = self.transition_mask.tobytes()
            self.block.setData(bufor)
            provider_save = QgsRasterFileWriter(filename).createOneBandRaster(Qgis.DataType.Byte,self.width,self.height,self.extent,self.raster1_layer_crs)
            provider_save.setEditable(True)
            provider_save.writeBlock(self.block, 1)
            provider_save.setEditable(False)
            QMessageBox.information(self, "Saved", f"Transition mask saved to:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{str(e)}")
