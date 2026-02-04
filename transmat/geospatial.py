from qgis.core import *
from qgis.gui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from qgis.utils import iface
import numpy as np
from osgeo import gdal
import tempfile
import os
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

    def calculate_transmat(self,raster1_layer:QgsRasterLayer, raster2_layer:QgsRasterLayer, null_value):
        # rasters must have the same crs, extent, and resolutions, both must have the same datatype
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
        raster1_band = int(self.raster1_band_combo.currentText())
        self.block = raster1_provider.block(raster1_band,self.extent,self.width,self.height)
        self.raster1_numpy = np.frombuffer(self.block.data(), dtype=numpy_dtype)
        self.raster1_numpy.shape = (self.height,self.width)

        # Convert raster2_layer to numpy array
        raster2_band = int(self.raster2_band_combo.currentText())
        self.block = raster2_provider.block(raster2_band,self.extent,self.width,self.height)
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
    
    def check_rasters(self, raster1_layer:QgsRasterLayer, raster2_layer:QgsRasterLayer):
        rast_warning = None

        if raster1_layer.dataProvider() == 0 or raster1_layer.dataProvider().ySize() == 0:
            rast_warning = f"{raster1_layer.name()} is empty."
            return rast_warning
        
        if raster2_layer.dataProvider() == 0 or raster2_layer.dataProvider().ySize() == 0:
            rast_warning = f"{raster2_layer.name()} is empty."
            return rast_warning

        if not raster1_layer.crs().isValid():
            rast_warning = f"{raster1_layer.name()} does not have a valid Coordinate Reference System (CRS)."
            return rast_warning
        
        if not raster2_layer.crs().isValid():
            rast_warning = f"{raster2_layer.name()} does not have a valid Coordinate Reference System (CRS)."
            return rast_warning
        
        if raster1_layer.crs() != raster2_layer.crs():
                rast_warning = f"{raster1_layer.name()} and {raster2_layer.name()} do not have the same Coordinate Reference System (CRS)."
                return rast_warning
        
        if raster1_layer.rasterUnitsPerPixelX() != raster2_layer.rasterUnitsPerPixelX() or raster1_layer.rasterUnitsPerPixelY() != raster2_layer.rasterUnitsPerPixelY():
            rast_warning = f"{raster1_layer.name()} and {raster2_layer.name()} do not have the same resolution."
            return rast_warning
        
        if raster1_layer.extent() != raster2_layer.extent():
            rast_warning = f"{raster1_layer.name()} and {raster2_layer.name()} do not have the same extent."
            return rast_warning
        
        if [raster1_layer.width(), raster1_layer.height()] != [raster2_layer.width(), raster2_layer.height()]:
            rast_warning = f"{raster1_layer.name()} and {raster2_layer.name()} do not have the same width and height."
            return rast_warning
        
        if raster1_layer.dataProvider().dataType(1) != raster2_layer.dataProvider().dataType(1):
            rast_warning = f"The values in {raster1_layer.name()} and {raster2_layer.name()} do not have the same datatype."
            return rast_warning

        return rast_warning

    def fix_rasters(self, raster1_layer:QgsRasterLayer, raster2_layer:QgsRasterLayer, default_raster:str):
        # Check if the rasters are empty
        if raster1_layer.dataProvider().xSize() == 0 or raster1_layer.dataProvider().ySize() == 0:
            return f"{raster1_layer.name()} is empty."
        
        if raster2_layer.dataProvider().xSize() == 0 or raster2_layer.dataProvider().ySize() == 0:
            return f"{raster2_layer.name()} is empty."

        # Check which raster to default to
        if default_raster == "Raster 1":
            default_raster = raster1_layer
            auxiliary_raster = raster2_layer
            default_raster_band = int(self.raster1_band_combo.currentText())
            auxiliary_raster_band = int(self.raster2_band_combo.currentText())
        else:
            default_raster = raster2_layer
            auxiliary_raster = raster1_layer
            default_raster_band = int(self.raster2_band_combo.currentText())
            auxiliary_raster_band = int(self.raster1_band_combo.currentText())

        # Assign crs to raster1 if needed
        if not default_raster.crs().isValid():
            default_raster.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        # Assign crs to raster1 if needed
        if not auxiliary_raster.crs().isValid():
            auxiliary_raster.setCrs(QgsCoordinateReferenceSystem("EPSG:4326")) 
        
        # Get the source of the auxiliary raster
        src_path1 = auxiliary_raster.source()

        # Create a temporary file on disk and get a file descriptor (fd) and its path (dst_path) and close it immediately (since we only need the file path)
        fd1, dst_path1 = tempfile.mkstemp(suffix=".tif")
        os.close(fd1)

        # Run GDAL Warp to change auxiliary_raster CRS, resolution and output datatype to the ones of the default raster. Change the default nodata value to the one defined by the user
        gdal.Warp(
            dst_path1,
            src_path1,
            srcSRS = auxiliary_raster.crs().authid(),
            dstSRS = default_raster.crs().authid(),
            srcNodata = auxiliary_raster.dataProvider().sourceNoDataValue(auxiliary_raster_band),
            dstNodata = self.na_spin.value(),
            xRes = default_raster.rasterUnitsPerPixelX(),
            yRes = default_raster.rasterUnitsPerPixelY(),
            outputType = default_raster.dataProvider().dataType(default_raster_band)
        )

        # Load the warped raster as a new QgsRasterLayer
        warped = QgsRasterLayer(dst_path1, f"{auxiliary_raster.name()}_warped")

        # Check validity
        if not warped.isValid():
            return "Could not harmonize the rasters."
        
        # Assign the new warped raster as the new auxiliary_raster
        auxiliary_raster = warped

        # you have to check the extent after warping to the same crs and then clip BOTH rasters to the extent
        # If the rasters have different extent find the intersection
        if default_raster.extent() != auxiliary_raster.extent():
            extent1 = default_raster.extent()
            extent2 = auxiliary_raster.extent()
            intersection = extent1.intersect(extent2)
            
            if intersection.isEmpty():
                return "Rasters do not overlap"
        else:
            intersection = default_raster.extent()

        # Clip the auxiliary raster to the intersection
        src_path2 = auxiliary_raster.source()
        fd2, dst_path2 = tempfile.mkstemp(suffix=".tif")
        os.close(fd2)

        gdal.Warp(
            dst_path2,
            src_path2,
            outputBounds = (
                intersection.xMinimum(),
                intersection.yMinimum(),
                intersection.xMaximum(),
                intersection.yMaximum(),
            ),
            outputBoundsSRS=default_raster.crs().authid(),
            xRes=default_raster.rasterUnitsPerPixelX(),
            yRes=default_raster.rasterUnitsPerPixelY(),
            dstNodata=self.na_spin.value(),
            outputType=default_raster.dataProvider().dataType(default_raster_band)
        )

        warped = QgsRasterLayer(dst_path2, f"{auxiliary_raster.name()}_warped")

        if not warped.isValid():
            return f"Could not clip {auxiliary_raster.name()} to the intersection of two rasters."
        
        auxiliary_raster = warped

        # Clip the default raster to the intersection and change the default nodata value to the one defined by the user
        src_path3 = default_raster.source()
        fd3, dst_path3 = tempfile.mkstemp(suffix=".tif")
        os.close(fd3)

        gdal.Warp(
            dst_path3,
            src_path3,
            srcNodata = default_raster.dataProvider().sourceNoDataValue(default_raster_band),
            dstNodata = self.na_spin.value(),
            outputBounds = (
                intersection.xMinimum(),
                intersection.yMinimum(),
                intersection.xMaximum(),
                intersection.yMaximum(),
            ),
            outputBoundsSRS=default_raster.crs().authid(),
            xRes=default_raster.rasterUnitsPerPixelX(),
            yRes=default_raster.rasterUnitsPerPixelY(),
            outputType=default_raster.dataProvider().dataType(default_raster_band)
        )

        warped = QgsRasterLayer(dst_path3, f"{default_raster.name()}_warped")

        if not warped.isValid():
            return f"Could not clip {default_raster.name()} to the intersection of two rasters."
        
        default_raster = warped

        return [default_raster, auxiliary_raster]
    
    def get_selection(self, row, column):
        index_to_value = {idx: val for val, idx in self.value_to_index.items()}

        row_value = index_to_value[row]
        column_value = index_to_value[column]

        raster1_numpy_selected = self.raster1_numpy == row_value
        raster2_numpy_selected = self.raster2_numpy == column_value

        self.transition_mask = np.logical_and(raster1_numpy_selected, raster2_numpy_selected)
        return self.transition_mask