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
        self.resize(800,900)
        self.setWindowTitle("Transmat")

        self.raster1_combo_label = QLabel("Raster 1")
        self.raster1_combo = QgsMapLayerComboBox()
        self.raster1_combo.setFilters(Qgis.LayerFilter.RasterLayer)

        self.raster1_band_label = QLabel("Raster 1 band")
        self.raster1_band_combo = QComboBox()

        self.raster2_combo_label = QLabel("Raster 2")
        self.raster2_combo = QgsMapLayerComboBox()
        self.raster2_combo.setFilters(Qgis.LayerFilter.RasterLayer)

        self.raster2_band_label = QLabel("Raster 2 band")
        self.raster2_band_combo = QComboBox()

        self.na_spin_label = QLabel("NA Value")
        self.na_spin = QSpinBox()
        self.na_spin.setMinimum(-9999)
        self.na_spin.setMaximum(9999)
        self.na_spin.setValue(0)

        # Auto-compatibility fix checkbox
        self.compatibility_checkbox = QCheckBox("Auto-compatibility fix")

        # QComboBox Label
        self.default_raster_combo_label = QLabel("Default raster")

        # QComboBox select raster to default to
        self.default_raster_combo = QComboBox()
        self.default_raster_combo.addItems(["Raster 1", "Raster 2"])

        # Calculate percentages checkbox
        self.percentage_checkbox = QCheckBox("Calculate percentages")

        # Button to generate matrix
        self.generate_btn = QPushButton("Generate Transition Matrix")

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
        self.harmonized_rasters_button = QPushButton("&Add Harmonized Rasters")
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.close_button)
        self.button_layout.addWidget(self.save_matrix_button)
        self.button_layout.addWidget(self.save_selection_button)
        self.button_layout.addWidget(self.harmonized_rasters_button)
        self.harmonized_rasters_button.hide()

        # Matrix table layout
        self.transition_counts = np.array([])
        table_top_label = QLabel("Raster 2")
        table_top_label.setAlignment(Qt.AlignCenter)
        table_left_label = QLabel("Raster 1")
        table_left_label.setAlignment(Qt.AlignCenter)
        self.table_widget = QTableWidget()
        self.table_layout = QGridLayout()
        self.table_layout.addWidget(table_top_label, 0, 1)
        self.table_layout.addWidget(table_left_label, 1, 0)
        self.table_layout.addWidget(self.table_widget, 1, 1)

        # Add to your main layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.raster1_combo_label)
        mainLayout.addWidget(self.raster1_combo)
        mainLayout.addWidget(self.raster1_band_label)
        mainLayout.addWidget(self.raster1_band_combo)
        mainLayout.addWidget(self.raster2_combo_label)
        mainLayout.addWidget(self.raster2_combo)
        mainLayout.addWidget(self.raster2_band_label)
        mainLayout.addWidget(self.raster2_band_combo)
        mainLayout.addWidget(self.na_spin_label)
        mainLayout.addWidget(self.na_spin)
        mainLayout.addWidget(self.compatibility_checkbox)
        mainLayout.addWidget(self.default_raster_combo_label)
        mainLayout.addWidget(self.default_raster_combo)
        mainLayout.addWidget(self.percentage_checkbox)
        mainLayout.addWidget(self.generate_btn)
        mainLayout.addLayout(self.table_layout)
        mainLayout.addWidget(self.transition_mask_tip_label, alignment=Qt.AlignCenter)
        mainLayout.addWidget(self.pixmap_label, alignment=Qt.AlignCenter)
        mainLayout.addLayout(self.button_layout)
        self.setLayout(mainLayout)

        # Turn on the Auto-compatibility fix by default
        self.compatibility_checkbox.setChecked(True)

        # Actions
        self.compatibility_checkbox.stateChanged.connect(self.toggle_visibility_defrast)
        self.generate_btn.clicked.connect(self.compute_transition_matrix)
        self.close_button.clicked.connect(self.close)
        self.save_matrix_button.clicked.connect(self.save_matrix)
        self.table_widget.cellClicked.connect(self.on_cell_clicked)
        self.save_selection_button.clicked.connect(self.save_transition_mask_as_tif)
        self.harmonized_rasters_button.clicked.connect(self.add_rasters)
        self.raster1_combo.layerChanged.connect(self.setup_raster1_band_combo)
        self.raster2_combo.layerChanged.connect(self.setup_raster2_band_combo)

        self.setup_raster1_band_combo()
        self.setup_raster2_band_combo()

    def toggle_visibility_defrast(self):
        if self.compatibility_checkbox.isChecked():
            self.default_raster_combo_label.show()
            self.default_raster_combo.show()
        else:
            self.default_raster_combo_label.hide()
            self.default_raster_combo.hide()

    def compute_transition_matrix(self):
        self.raster1_layer = self.raster1_combo.currentLayer()
        self.raster2_layer = self.raster2_combo.currentLayer()
        null_value = self.na_spin.value()

        if not self.raster1_layer or not self.raster2_layer:
            QMessageBox.warning(self, "Missing Input", "Please select two raster layers.")
            return
        
        # Check the raster compatibility
        rast_check = renderer.check_rasters(self, self.raster1_layer, self.raster2_layer)
        fixed_layers = None
        # If it is not none there is a compatibility problem
        if rast_check is not None:
            # If auto-compatibility is enabled try to fix the rasters
            if self.compatibility_checkbox.isChecked():
                fixed_layers = renderer.fix_rasters(self, self.raster1_layer, self.raster2_layer, self.default_raster_combo.currentText())
                # If string is returned the harmonisation was not successful
                if isinstance(fixed_layers, str):
                    QMessageBox.critical(self, "Auto-compatibility fix failed", fixed_layers)
                    return
                idx = 0 if self.default_raster_combo.currentText() == "Raster 1" else 1
                self.raster1_layer, self.raster2_layer = fixed_layers[idx], fixed_layers[1 - idx]
            else:
                QMessageBox.warning(self, "Raster Layer Error" ,rast_check)
                return

        matrix = renderer.calculate_transmat(self, self.raster1_layer, self.raster2_layer, null_value)
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

        if isinstance(fixed_layers, list):
            self.harmonized_rasters_button.show()
        else:
            self.harmonized_rasters_button.hide()
    
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

    def add_rasters(self):
        self.raster1_layer.setName("Raster 1")
        self.raster2_layer.setName("Raster 2")
        QgsProject.instance().addMapLayer(self.raster1_layer)
        QgsProject.instance().addMapLayer(self.raster2_layer)

    def setup_raster1_band_combo(self):
        raster1_layer = self.raster1_combo.currentLayer()
        if raster1_layer is None:
            return 
        raster1_band_number = raster1_layer.bandCount()
        
        self.raster1_band_combo.clear()
        self.raster1_band_combo.addItems([str(i) for i in range(1, raster1_band_number + 1)])

    def setup_raster2_band_combo(self):
        raster2_layer = self.raster2_combo.currentLayer()
        if raster2_layer is None:
            return 
        raster2_band_number = raster2_layer.bandCount()
        
        self.raster2_band_combo.clear()
        self.raster2_band_combo.addItems([str(i) for i in range(1, raster2_band_number + 1)])