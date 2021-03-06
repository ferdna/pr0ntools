#!/usr/bin/python
'''
pr0nhugin: allows editing a reduced project to speed up hugin editing
Copyright 2012 John McMaster <JohnDMcMaster@gmail.com>
Licensed under a 2 clause BSD license, see COPYING for details
'''

import argparse
from pr0ntools.stitch.pto.project import PTOProject
from pr0ntools.stitch.image_coordinate_map import ImageCoordinateMap
import subprocess
import shutil

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='create tiles from unstitched images')
    parser.add_argument('--border', default='1', help='border size')
    parser.add_argument('pto', default='out.pto', nargs='?', help='pto project')
    args = parser.parse_args()
    args.border = int(args.border, 0)
    
    pto_orig = PTOProject.from_file_name(args.pto)
    img_fns = []
    for il in pto_orig.get_image_lines():
        img_fns.append(il.get_name())
    icm = ImageCoordinateMap.from_tagged_file_names(img_fns)
    
    # Reduced .pto
    pto_red = pto_orig.copy()
    # Delete all lines not in the peripheral
    pto_orig.build_image_fn_map()
    ils_del = []
    for y in xrange(args.border, icm.height() - args.border):
        for x in xrange(args.border, icm.width() - args.border):
            im = icm.get_image(x, y)
            if im is None:
                continue
            ils_del.append(pto_orig.img_fn2il[im])
    print 'Deleting %d / %d images' % (len(ils_del), icm.width() * icm.height())
    pto_red.del_images(ils_del)
    pto_red.save_as(pto_orig.file_name.replace('.pto', '_sm.pto'), is_new_filename=True)

    print 'Opening temp file %s' % pto_red.file_name
    subp = subprocess.Popen(['hugin', pto_red.file_name], shell=False)
    subp.communicate()
    print 'Hugin exited with code %d' % subp.returncode

    pto_red.reopen()

    # has crop + dimensions
    # p f0 w2673 h2056 v76  E0 R0 S100,2673,100,2056 n"TIFF_m c:LZW"
    print 'Replacing p line...'
    pto_orig.panorama_line = pto_red.panorama_line

    # shouldn't be necessary but just in case
    print 'Replacing m line...'
    pto_orig.mode_line = pto_red.mode_line

    # copy over rotation
    # assume its the same for all
    r = pto_red.image_lines[0].getv('r')
    if r is None:
        r = 0.0
    def floats(f):
        if f is None:
            return 'None'
        else:
            return '%0.2f' % f
    print 'Rotation %s => %s' % (floats(pto_orig.image_lines[0].getv('r')), floats(r))
    for il in pto_orig.image_lines:
        il.setv('r', r)

    print 'Saving final project'
    # small backup in case something went wrong
    shutil.copy(pto_orig.file_name, '/tmp/pr0n-prehugin.pto')
    pto_orig.save_as(pto_orig.file_name)

    print 'Done!'
