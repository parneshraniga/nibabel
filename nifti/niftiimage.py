#emacs: -*- mode: python-mode; py-indent-offset: 4; indent-tabs-mode: nil -*-
#ex: set sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyNIfTI package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Python class representation of a NIfTI image"""

__docformat__ = 'restructuredtext'


# the swig wrapper if the NIfTI C library
import nifti.nifticlib as nifticlib
from nifti.niftiformat import NiftiFormat
from nifti.utils import splitFilename
import numpy as N


class NiftiImage(NiftiFormat):
    """Wrapper class for convenient access to NIfTI data.

    The class can either load an image from file or convert a NumPy ndarray
    into a NIfTI file structure. Either way is automatically determined
    by the type of the 'source' argument. If `source` is a string, it is
    assumed to be a filename an ndarray is treated as such.

    One can optionally specify whether the image data should be loaded into
    memory when opening NIfTI data from files (`load`). When converting a NumPy
    array one can optionally specify a dictionary with NIfTI header data as
    available via the `header` attribute.

    Alternatively, uncompressed NIfTI images can also be memory-mapped. This
    is the preferred method whenever only a small part of the image data has
    to be accessed or the memory is not sufficient to load the whole dataset.
    Please note, that memory-mapping is not required when exclusively header
    information shall be accessed. By default no image data is loaded into
    memory.
    """



    def __init__(self, source, header={}, load=False):
        """Create a NiftiImage object.

        This method decides whether to load a nifti image from file or create
        one from ndarray data, depending on the datatype of `source`.

        :Parameters:
            source: str | ndarray
                If source is a string, it is assumed to be a filename and an
                attempt will be made to open the corresponding NIfTI file.
                In case of an ndarray the array data will be used for the to be
                created nifti image and a matching nifti header is generated.
                If an object of a different type is supplied as 'source' a
                ValueError exception will be thrown.
            header: dict
                Additonal header data might be supplied. However,
                dimensionality and datatype are determined from the ndarray and
                not taken from a header dictionary.
            load: Boolean
                If set to True the image data will be loaded into memory. This
                is only useful if loading a NIfTI image from file.
            mmap: Boolean
                Enabled memory mapped access to an image file. This only works
                with uncompressed NIfTI files. This setting will be ignored
                if 'load' is set to true.
        """
        # setup all nifti header related stuff
        NiftiFormat.__init__(self, source, header)

        # where the data will go to
        self.__data = None

        # load data
        if type(source) == N.ndarray:
            # assign data from source array
            self.__data = data[:]
        elif type(source) == str:
            # only load image data from file if requested
            if load:
                self.load()
        else:
            raise ValueError, \
                  "Unsupported source type. Only NumPy arrays and filename " \
                  + "string are supported."


    def __del__(self):
        """Do all necessary cleanups by calling.
        Close the file and free all unnecessary memory.
        """
        self.unload()


    def save(self, filename=None, filetype = 'NIFTI'):
        """Save the image.

        If the image was created using array data (not loaded from a file) one
        has to specify a filename.

        Warning: There will be no exception if writing fails for any reason,
        as the underlying function nifti_write_hdr_img() from libniftiio does
        not provide any feedback. Suggestions for improvements are appreciated.

        If not yet done already, the image data will be loaded into memory
        before saving the file.

        :Parameters:
            filename: str | None
                Calling save() with `filename` equal None on a NiftiImage
                loaded from a file, it will overwrite the original file.

                Usually setting the filename also determines the filetype
                (NIfTI/ANALYZE). Please see the documentation of the
                `setFilename()` method for some more details.
            filetype: str
                Override filetype. Please see the documentation of the
                `setFilename()` method for some more details.
        """

        # If image data is not yet loaded, do it now.
        # It is important to do it already here, because nifti_image_load
        # depends on the correct filename set in the nifti_image struct
        # and this will be modified in this function!
        self.load()

        # set a default description if there is none
        if not self.description:
            self.description = 'Created with PyNIfTI'

        # update header information
        self.updateCalMinMax()

        # saving for the first time?
        if not self.filename or filename:
            if not filename:
                raise ValueError, \
                      "When saving an image for the first time a filename " \
                      + "has to be specified."

            self.setFilename(filename, filetype)

        # now save it
        nifticlib.nifti_image_write_hdr_img(self.raw_nimg, 1, 'wb')
        # yoh comment: unfortunately return value of nifti_image_write_hdr_img
        # can't be used to track the successful completion of save
        # raise IOError, 'An error occured while attempting to save the image
        # file.'


    def __haveImageData(self):
        """Returns if the image data is accessible -- either loaded into
        memory or memory mapped.

        See: `load()`, `unload()`
        """
        return (not self.__data == None)


    def load(self):
        """Load the image data into memory, if it is not already accessible.

        It is save to call this method several times successively.
        """
        # do nothing if there already is data
        # which included memory mapped arrays not just data in memory
        if self.__haveImageData():
            return

        if nifticlib.nifti_image_load( self.raw_nimg ) < 0:
            raise RuntimeError, "Unable to load image data."

        self.__data = nifticlib.wrapImageDataWithArray(self.raw_nimg)


    def unload(self):
        """Unload image data and free allocated memory.

        This methods does nothing in case of memory mapped files.
        """
        # if no filename is se, the data will be lost and cannot be recovered
        if not self.filename:
            raise RuntimeError, \
                  "No filename is set, unloading the data would " \
                  "loose it completely without a chance of recovery."

        nifticlib.nifti_image_unload(self.raw_nimg)

        # reset array storage, as data pointer became invalid
        self.__data = None


    def getDataArray(self):
        """Return the NIfTI image data wrapped into a NumPy array.

        Attention: The array shares the data with the NiftiImage object. Any
        resize operation or datatype conversion will most likely result in a
        fatal error. If you need to perform such things, get a copy
        of the image data by using `asarray(copy=True)`.

        The `data` property is an alternative way to access this function.
        """
        return self.asarray(False)


    def asarray(self, copy = True):
        """Convert the image data into a ndarray.

        :Parameters:
            copy: Boolean
                If set to False the array only wraps the image data. Any
                modification done to the array is also done to the image data.
                In this case changing the shape, size or datatype of a wrapping
                array is not supported and will most likely result in a fatal
                error. If you want to do anything else to the data but reading
                or simple value assignment use a copy of the data by setting
                the copy flag to True. Later you can convert the modified data
                array into a NIfTi file again.
        """
        # make sure data is accessible
        self.load()

        if copy:
            return self.__data.copy()
        else:
            return self.__data


    def getScaledData(self):
        """Returns a scaled copy of the data array.

        Scaling is done by multiplying with the slope and adding the intercept
        that is stored in the NIfTI header.

        :Returns:
            ndarray
        """
        data = self.asarray(copy = True)

        return data * self.slope + self.intercept


    def updateCalMinMax(self):
        """Update the image data maximum and minimum value in the nifti header.
        """
        self.raw_nimg.cal_max = float(self.data.max())
        self.raw_nimg.cal_min = float(self.data.min())


    def getHeader(self):
        """Returns the header data of the `NiftiImage` in a dictionary.

        Note, that modifications done to this dictionary do not cause any
        modifications in the NIfTI image. Please use the `updateHeader()`
        method to apply changes to the image.

        The `header` property is an alternative way to access this function. 
        But please note that the `header` property cannot be used like this::

            nimg.header['something'] = 'new value'

        Instead one has to get the header dictionary, modify and later reassign
        it::

            h = nimg.header
            h['something'] = 'new value'
            nimg.header = h
        """
        h = {}

        # Convert nifti_image struct into nifti1 header struct.
        # This get us all data that will actually make it into a
        # NIfTI file.
        nhdr = nifticlib.nifti_convert_nim2nhdr(self.raw_nimg)

        return NiftiImage.nhdr2dict(nhdr)


    def updateHeader(self, hdrdict):
        """Update NIfTI header information.

        Updated header data is read from the supplied dictionary. One cannot
        modify dimensionality and datatype of the image data. If such
        information is present in the header dictionary it is removed before
        the update. If resizing or datatype casting are required one has to 
        convert the image data into a separate array (`NiftiImage.assarray()`)
        and perform resize and data manipulations on this array. When finished,
        the array can be converted into a nifti file by calling the NiftiImage
        constructor with the modified array as 'source' and the nifti header
        of the original NiftiImage object as 'header'.

        It is save to call this method with and without loaded image data.

        The actual update is done by `NiftiImage.updateNiftiHeaderFromDict()`.
        """
        # rebuild nifti header from current image struct
        nhdr = nifticlib.nifti_convert_nim2nhdr(self.raw_nimg)

        # remove settings from the hdrdict that are determined by
        # the data set and must not be modified to preserve data integrity
        if hdrdict.has_key('datatype'):
            del hdrdict['datatype']
        if hdrdict.has_key('dim'):
            del hdrdict['dim']

        # update the nifti header
        NiftiImage.updateNiftiHeaderFromDict(nhdr, hdrdict)

        # if no filename was set already (e.g. image from array) set a temp
        # name now, as otherwise nifti_convert_nhdr2nim will fail
        have_temp_filename = False
        if not self.filename:
            self.filename = 'pynifti_updateheader_temp_name'
            have_temp_filename = True

        # recreate nifti image struct
        new_nimg = nifticlib.nifti_convert_nhdr2nim(nhdr, self.filename)
        if not new_nimg:
            raise RuntimeError, \
                  "Could not recreate NIfTI image struct from updated header."

        # replace old image struct by new one
        # be careful with memory leak (still not checked whether successful)

        # rescue data ptr
        new_nimg.data = self.raw_nimg.data

        # and remove it from old image struct
        self.raw_nimg.data = None

        # to be able to call the cleanup function without lossing the data
#        self._close()

        # assign the new image struct
        self.raw_nimg = new_nimg

        # reset filename if temp name was set
        if have_temp_filename:
            self.filename = ''


    def setSlope(self, value):
        """Set the slope attribute in the NIfTI header.

        Besides reading it is also possible to set the slope by assigning
        to the `slope` property.
        """
        self.raw_nimg.scl_slope = float(value)


    def setIntercept(self, value):
        """Set the intercept attribute in the NIfTI header.

        Besides reading it is also possible to set the intercept by assigning
        to the `intercept` property.
        """
        self.raw_nimg.scl_inter = float(value)


    def setDescription(self, value):
        """Set the description element in the NIfTI header.

        :Parameter:
            value: str
                Description -- must not be longer than 79 characters.

        Besides reading it is also possible to set the description by assigning
        to the `description` property.
        """
        if len(value) > 79:
            raise ValueError, \
                  "The NIfTI format only supports descriptions shorter than " \
                  + "80 chars."

        self.raw_nimg.descrip = value


    def getSForm(self):
        """Returns the sform matrix.

        Please note, that the returned SForm matrix is not bound to the
        NiftiImage object. Therefore it cannot be successfully modified
        in-place. Modifications to the SForm matrix can only be done by setting
        a new SForm matrix either by calling `setSForm()` or by assigning it to
        the `sform` attribute.

        The `sform` property is an alternative way to access this function.
        """
        return nifticlib.mat442array(self.raw_nimg.sto_xyz)


    def setSForm(self, m):
        """Sets the sform matrix.

        The supplied value has to be a 4x4 matrix. The matrix elements will be
        converted to floats. By definition the last row of the sform matrix has
        to be (0,0,0,1). However, different values can be assigned, but will
        not be stored when the niftifile is saved.

        The inverse sform matrix will be automatically recalculated.

        Besides reading it is also possible to set the sform matrix by
        assigning to the `sform` property.
        """
        if m.shape != (4, 4):
            raise ValueError, "SForm matrix has to be of size 4x4."

        # make sure it is float
        m = m.astype('float')

        nifticlib.set_mat44( self.raw_nimg.sto_xyz,
                         m[0,0], m[0,1], m[0,2], m[0,3],
                         m[1,0], m[1,1], m[1,2], m[1,3],
                         m[2,0], m[2,1], m[2,2], m[2,3],
                         m[3,0], m[3,1], m[3,2], m[3,3] )

        # recalculate inverse
        self.raw_nimg.sto_ijk = \
            nifticlib.nifti_mat44_inverse( self.raw_nimg.sto_xyz )


    def getInverseSForm(self):
        """Returns the inverse sform matrix.

        Please note, that the inverse SForm matrix cannot be modified in-place.
        One needs to set a new SForm matrix instead. The corresponding inverse
        matrix is then re-calculated automatically.

        The `sform_inv` property is an alternative way to access this function.
        """
        return nifticlib.mat442array(self.raw_nimg.sto_ijk)


    def getQForm(self):
        """Returns the qform matrix.

        Please note, that the returned QForm matrix is not bound to the
        NiftiImage object. Therefore it cannot be successfully modified
        in-place. Modifications to the QForm matrix can only be done by setting
        a new QForm matrix either by calling `setQForm()` or by assigning it to
        the `qform` property.
        """
        return nifticlib.mat442array(self.raw_nimg.qto_xyz)


    def getInverseQForm(self):
        """Returns the inverse qform matrix.

        The `qform_inv` property is an alternative way to access this function.

        Please note, that the inverse QForm matrix cannot be modified in-place.
        One needs to set a new QForm matrix instead. The corresponding inverse
        matrix is then re-calculated automatically.
        """
        return nifticlib.mat442array(self.raw_nimg.qto_ijk)


    def setQForm(self, m):
        """Sets the qform matrix.

        The supplied value has to be a 4x4 matrix. The matrix will be converted
        to float.

        The inverse qform matrix and the quaternion representation will be
        automatically recalculated.

        Besides reading it is also possible to set the qform matrix by
        assigning to the `qform` property.
        """
        if m.shape != (4, 4):
            raise ValueError, "QForm matrix has to be of size 4x4."

        # make sure it is float
        m = m.astype('float')

        nifticlib.set_mat44( self.raw_nimg.qto_xyz,
                         m[0,0], m[0,1], m[0,2], m[0,3],
                         m[1,0], m[1,1], m[1,2], m[1,3],
                         m[2,0], m[2,1], m[2,2], m[2,3],
                         m[3,0], m[3,1], m[3,2], m[3,3] )

        # recalculate inverse
        self.raw_nimg.qto_ijk = \
            nifticlib.nifti_mat44_inverse( self.raw_nimg.qto_xyz )

        # update quaternions
        (self.raw_nimg.quatern_b,
         self.raw_nimg.quatern_c,
         self.raw_nimg.quatern_d,
         self.raw_nimg.qoffset_x,
         self.raw_nimg.qoffset_y,
         self.raw_nimg.qoffset_z,
         self.raw_nimg.dx,
         self.raw_nimg.dy,
         self.raw_nimg.dz,
         self.raw_nimg.qfac) = \
           nifticlib.nifti_mat44_to_quatern( self.raw_nimg.qto_xyz )


    def updateQFormFromQuaternion(self):
        """Recalculates the qform matrix (and the inverse) from the quaternion
        representation.
        """
        # recalculate qform
        self.raw_nimg.qto_xyz = nifticlib.nifti_quatern_to_mat44(
          self.raw_nimg.quatern_b,
          self.raw_nimg.quatern_c,
          self.raw_nimg.quatern_d,
          self.raw_nimg.qoffset_x,
          self.raw_nimg.qoffset_y,
          self.raw_nimg.qoffset_z,
          self.raw_nimg.dx,
          self.raw_nimg.dy,
          self.raw_nimg.dz,
          self.raw_nimg.qfac)


        # recalculate inverse
        self.raw_nimg.qto_ijk = \
            nifticlib.nifti_mat44_inverse( self.raw_nimg.qto_xyz )


    def setQuaternion(self, value):
        """Set Quaternion from 3-tuple (qb, qc, qd).

        The qform matrix and it's inverse are re-computed automatically.

        Besides reading it is also possible to set the quaternion by assigning
        to the `quatern` property.
        """
        if len(value) != 3:
            raise ValueError, 'Requires 3-tuple.'

        self.raw_nimg.quatern_b = float(value[0])
        self.raw_nimg.quatern_c = float(value[1])
        self.raw_nimg.quatern_d = float(value[2])

        self.updateQFormFromQuaternion()


    def getQuaternion(self):
        """Returns a 3-tuple containing (qb, qc, qd).

        The `quatern` property is an alternative way to access this function.
        """
        return((self.raw_nimg.quatern_b,
                self.raw_nimg.quatern_c,
                self.raw_nimg.quatern_d))


    def setQOffset(self, value):
        """Set QOffset from 3-tuple (qx, qy, qz).

        The qform matrix and its inverse are re-computed automatically.

        Besides reading it is also possible to set the qoffset by assigning
        to the `qoffset` property.
        """
        if len(value) != 3:
            raise ValueError, 'Requires 3-tuple.'

        self.raw_nimg.qoffset_x = float(value[0])
        self.raw_nimg.qoffset_y = float(value[1])
        self.raw_nimg.qoffset_z = float(value[2])

        self.updateQFormFromQuaternion()


    def getQOffset(self):
        """Returns a 3-tuple containing (qx, qy, qz).

        The `qoffset` property is an alternative way to access this function.
        """
        return( ( self.raw_nimg.qoffset_x,
                  self.raw_nimg.qoffset_y,
                  self.raw_nimg.qoffset_z ) )


    def setQFac(self, value):
        """Set qfac.

        The qform matrix and its inverse are re-computed automatically.

        Besides reading it is also possible to set the qfac by assigning
        to the `qfac` property.
        """
        self.raw_nimg.qfac = float(value)
        self.updateQFormFromQuaternion()


    def getQOrientation(self, as_string = False):
        """Returns to orientation of the i, j and k axis as stored in the
        qform matrix.

        By default NIfTI orientation codes are returned, but if `as_string` is
        set to true a string representation ala 'Left-to-right' is returned
        instead.
        """
        codes = nifticlib.nifti_mat44_to_orientation(self.raw_nimg.qto_xyz)
        if as_string:
            return [ nifticlib.nifti_orientation_string(i) for i in codes ]
        else:
            return codes


    def getSOrientation(self, as_string = False):
        """Returns to orientation of the i, j and k axis as stored in the
        sform matrix.

        By default NIfTI orientation codes are returned, but if `as_string` is
        set to true a string representation ala 'Left-to-right' is returned
        instead.
        """
        codes = nifticlib.nifti_mat44_to_orientation(self.raw_nimg.sto_xyz)
        if as_string:
            return [ nifticlib.nifti_orientation_string(i) for i in codes ]
        else:
            return codes


    def getBoundingBox(self):
        """Get the bounding box of the image.

        This functions returns a tuple of (min, max) tuples. It contains as
        many tuples as image dimensions. The order of dimensions is identical
        to that in the data array.

        The `bbox` property is an alternative way to access this function.
        """
        nz = self.data.squeeze().nonzero()

        bbox = []

        for dim in nz:
            bbox.append( ( dim.min(), dim.max() ) )

        return tuple(bbox)


    def setFilename(self, filename, filetype = 'NIFTI'):
        """Set the filename for the NIfTI image.

        Setting the filename also determines the filetype. If the filename
        ends with '.nii' the type will be set to NIfTI single file. A '.hdr'
        extension can be used for NIfTI file pairs. If the desired filetype
        is ANALYZE the extension should be '.img'. However, one can use the
        '.hdr' extension and force the filetype to ANALYZE by setting the
        filetype argument to ANALYZE. Setting filetype if the filename
        extension is '.nii' has no effect, the file will always be in NIFTI
        format.

        If the filename carries an additional '.gz' the resulting file(s) will
        be compressed.

        Uncompressed NIfTI single files are the default filetype that will be
        used if the filename has no valid extension. The '.nii' extension is
        appended automatically. The 'filetype' argument can be used to force a
        certain filetype when no extension can be used to determine it. 
        'filetype' can be one of the nifticlibs filtetypes or any of 'NIFTI',
        'NIFTI_GZ', 'NIFTI_PAIR', 'NIFTI_PAIR_GZ', 'ANALYZE', 'ANALYZE_GZ'.

        Setting the filename will cause the image data to be loaded into memory
        if not yet done already. This has to be done, because without the
        filename of the original image file there would be no access to the
        image data anymore. As a side-effect a simple operation like setting a
        filename may take a significant amount of time (e.g. for a large 4d
        dataset).

        By passing an empty string or none as filename one can reset the
        filename and detach the NiftiImage object from any file on disk.

        Examples:

          Filename          Output of save()
          ----------------------------------
          exmpl.nii         exmpl.nii (NIfTI)
          exmpl.hdr         exmpl.hdr, exmpl.img (NIfTI)
          exmpl.img         exmpl.hdr, exmpl.img (ANALYZE)
          exmpl             exmpl.nii (NIfTI)
          exmpl.hdr.gz      exmpl.hdr.gz, exmpl.img.gz (NIfTI)

        ! exmpl.gz          exmpl.gz.nii (uncompressed NIfTI)

        Setting the filename is also possible by assigning to the 'filename'
        property.
        """
        # If image data is not yet loaded, do it now.
        # It is important to do it already here, because nifti_image_load
        # depends on the correct filename set in the nifti_image struct
        # and this will be modified in this function!
        self.load()

        # if no filename is given simply reset it to nothing
        if not filename:
            self.raw_nimg.fname = ''
            self.raw_nimg.iname = ''
            return

        # separate basename and extension
        base, ext = splitFilename(filename)

        # if no extension default to nifti single files
        if ext == '': 
            if filetype == 'NIFTI' \
               or filetype == nifticlib.NIFTI_FTYPE_NIFTI1_1:
                ext = 'nii'
            elif filetype == 'NIFTI_PAIR' \
                 or filetype == nifticlib.NIFTI_FTYPE_NIFTI1_2:
                ext = 'hdr'
            elif filetype == 'ANALYZE' \
                 or filetype == nifticlib.NIFTI_FTYPE_ANALYZE:
                ext = 'img'
            elif filetype == 'NIFTI_GZ':
                ext = 'nii.gz'
            elif filetype == 'NIFTI_PAIR_GZ':
                ext = 'hdr.gz'
            elif filetype == 'ANALYZE_GZ':
                ext = 'img.gz'
            else:
                raise RuntimeError, "Unhandled filetype."

        # Determine the filetype and set header and image filename
        # appropriately.

        # nifti single files are easy
        if ext == 'nii.gz' or ext == 'nii':
            self.raw_nimg.fname = base + '.' + ext
            self.raw_nimg.iname = base + '.' + ext
            self.raw_nimg.nifti_type = nifticlib.NIFTI_FTYPE_NIFTI1_1
        # uncompressed nifti file pairs
        elif ext in [ 'hdr', 'img' ]:
            self.raw_nimg.fname = base + '.hdr'
            self.raw_nimg.iname = base + '.img'
            if ext == 'hdr' and not filetype.startswith('ANALYZE'):
                self.raw_nimg.nifti_type = nifticlib.NIFTI_FTYPE_NIFTI1_2
            else:
                self.raw_nimg.nifti_type = nifticlib.NIFTI_FTYPE_ANALYZE
        # compressed file pairs
        elif ext in [ 'hdr.gz', 'img.gz' ]:
            self.raw_nimg.fname = base + '.hdr.gz'
            self.raw_nimg.iname = base + '.img.gz'
            if ext == 'hdr.gz' and not filetype.startswith('ANALYZE'):
                self.raw_nimg.nifti_type = nifticlib.NIFTI_FTYPE_NIFTI1_2
            else:
                self.raw_nimg.nifti_type = nifticlib.NIFTI_FTYPE_ANALYZE
        else:
            raise RuntimeError, "Unhandled filetype."


    def getFilename(self):
        """Returns the filename.

        To be consistent with `setFilename()` the image filename is returned
        for ANALYZE images while the header filename is returned for NIfTI
        files.

        The `filename` property is an alternative way to access this function.
        """
        if self.raw_nimg.nifti_type == nifticlib.NIFTI_FTYPE_ANALYZE:
            return self.raw_nimg.iname
        else:
            return self.raw_nimg.fname

    # class properties
    # read only
    data =          property(fget=getDataArray)
    bbox =          property(fget=getBoundingBox)

    # read and write
    header =        property(fget=getHeader, fset=updateHeader)

