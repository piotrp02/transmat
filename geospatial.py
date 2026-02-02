from qgis.core import *
from qgis.gui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from qgis.utils import iface
import numpy as np
gdal_to_numpy = {
    1: np.uint8,     # Byte
    2: np.uint16,    # UInt16
    3: np.int16,     # Int16
    4: np.uint32,    # UInt32
    5: np.int32,     # Int32
    6: np.float32,   # Float32
    7: np.float64,   # Float64
    10: np.complex64,   # CFloat32
    11: np.complex128,  # CFloat64
}

class renderer:
    def __init__(self):
        self.settings = QgsMapSettings()
        self.current_raster1_layer = None
        self.current_raster2_layer = None
        self.n_classes = 1
        self.unique_values = None
        self.value_to_index = None

    def calculate_transmat(self,raster1_layer:QgsGeometry, raster2_layer:QgsGeometry, null_value):
        # rasters must have the same crs, extent, and resolutions, both must have the same datatype and have only one band
        raster1_provider = raster1_layer.dataProvider()
        raster2_provider = raster2_layer.dataProvider()

        # Prepare common metadata for both layers
        self.width = raster1_layer.width()
        self.height = raster1_layer.height()
        self.extent = raster1_layer.extent()
        qgis_dtype = raster1_provider.dataType(1)
        numpy_dtype = gdal_to_numpy.get(qgis_dtype, np.float32)
        self.raster1_layer_crs = raster1_layer.crs()

        # Convert raster1_layer to numpy array
        self.block = raster1_provider.block(1,self.extent,self.width,self.height)
        self.raster1_numpy = np.frombuffer(self.block.data(), dtype=numpy_dtype)
        self.raster1_numpy.shape = (self.height,self.width)

        # Convert raster2_layer to numpy array
        self.block = raster2_provider.block(1,self.extent,self.width,self.height)
        self.raster2_numpy = np.frombuffer(self.block.data(), dtype=numpy_dtype)
        self.raster2_numpy.shape = (self.height,self.width)

        # Flatten the arrays
        raster1_flat = self.raster1_numpy.flatten()
        raster2_flat = self.raster2_numpy.flatten()

        # Get the number of classes
        combined = np.concatenate([raster1_flat, raster2_flat])
        self.unique_values = np.unique(combined)
        self.unique_values = self.unique_values[self.unique_values != null_value]
        self.n_classes = self.unique_values.size

        # Map raster values to indices
        self.value_to_index = {val: idx for idx, val in enumerate(self.unique_values)}

        # Create a 2D histogram to count the transitions
        self.transition_counts = np.zeros((self.n_classes, self.n_classes), dtype=int)

        # Count transitions
        for old_val, new_val in zip(raster1_flat, raster2_flat):
            if old_val != null_value and new_val != null_value:
                i = self.value_to_index[old_val]
                j = self.value_to_index[new_val]
                self.transition_counts[i, j] += 1

        return self.transition_counts
    
    def check_rasters(self, raster1_layer:QgsGeometry, raster2_layer:QgsGeometry):
        rast_warning = None
        if not raster1_layer.crs().isValid():
            rast_warning = f"{raster1_layer.name()} does not have a valid Coordinate Reference System (CRS)."
            return rast_warning
        
        if not raster2_layer.crs().isValid():
            rast_warning = f"{raster2_layer.name()} does not have a valid Coordinate Reference System (CRS)."
            return rast_warning
        
        if raster1_layer.crs() != raster2_layer.crs():
            rast_warning = f"{raster1_layer.name()} and {raster2_layer.name()} do not have the same Coordinate Reference System (CRS)."
            return rast_warning
        
        if raster1_layer.extent() != raster2_layer.extent():
            rast_warning = f"{raster1_layer.name()} and {raster2_layer.name()} do not have the same extent."
            return rast_warning
        
        if [raster1_layer.width(), raster1_layer.height()] != [raster2_layer.width(), raster2_layer.height()]:
            rast_warning = f"{raster1_layer.name()} and {raster2_layer.name()} do not have the same width and height."
            return rast_warning

        if [raster1_layer.width(), raster1_layer.height()] != [raster2_layer.width(), raster2_layer.height()]:
            rast_warning = f"{raster1_layer.name()} and {raster2_layer.name()} do not have the same width and height."
            return rast_warning
        
        if raster1_layer.dataProvider().dataType(1) != raster2_layer.dataProvider().dataType(1):
            rast_warning = f"The values in {raster1_layer.name()} and {raster2_layer.name()} do not have the same datatype."
            return rast_warning

        return rast_warning
    
    def get_selection(self, row, column):
        index_to_value = {idx: val for val, idx in self.value_to_index.items()}

        row_value = index_to_value[row]
        column_value = index_to_value[column]

        raster1_numpy_selected = self.raster1_numpy == row_value
        raster2_numpy_selected = self.raster2_numpy == column_value

        self.transition_mask = np.logical_and(raster1_numpy_selected, raster2_numpy_selected)
        return self.transition_mask