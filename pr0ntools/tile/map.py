from pr0ntools.pimage import PImage
from pr0ntools.tile.tile import SingleTiler, TileTiler, calc_max_level
from pr0ntools.stitch.image_coordinate_map import ImageCoordinateMap
import os
import os.path
import math

'''
Source data for map
Two options:
-A large input image
-Pre-generated tiles (as generated by stitch)
'''
class MapSource:
	def __init__(self):
		self.set_out_extension('.jpg')
	
	def set_out_extension(self, s):
		self.out_extension = s
	
	def width(self):
		return None

	def height(self):
		return None
		
	def calc_max_level(self):
		return calc_max_level(self.height(), self.width())
				
	def generate_tiles(self, max_level, min_level, dst_basedir):
		pass
		
# Input to map generator algorithm is a large input image
class ImageMapSource(MapSource):
	def __init__(self, image_in):
		self.image_in = image_in
		self.image = PImage.from_file(self.image_in)
		self.set_out_extension('.jpg')

	def get_name(self):
		return self.image_in.split('.')[0]

	def set_out_extension(self, s):
		self.out_extension = s

	def width(self):
		return self.image.width()
		
	def height(self):
		return self.image.height()
	
	def generate_tiles(self, max_level, min_level, dst_basedir):
		# Generate tiles
		print 'From single image in %s to dir %s' % (self.image_in, dst_basedir)
		gen = SingleTiler(self.image_in, max_level, min_level, dst_basedir=dst_basedir)
		gen.set_out_extension(self.out_extension)
		gen.run()
	
class TileMapSource(MapSource):
	def __init__(self, dir_in, threads=1):
		print 'TileMapSource()'
		self.tw = 250
		self.th = 250
		self.threads = threads
		
		self.file_names = set()
		for f in os.listdir(dir_in):
			self.file_names.add(dir_in + "/" + f)
		self.src_dir = dir_in
		
		self.map = ImageCoordinateMap.from_tagged_file_names(self.file_names)
		
		self.x_tiles = self.map.width()
		self.y_tiles = self.map.height()
		
		print 'Tile canvas width %d, height %d' % (self.width(), self.height())
		
		MapSource.__init__(self)
	
	def get_name(self):
		# Get the last directory component
		ret = os.path.basename(self.src_dir)
		if ret == '.' or ret == '..':
			ret = 'unknown'
		return ret
		
	def width(self):
		return self.tw * self.x_tiles
		
	def height(self):
		return self.th * self.y_tiles
	
	def generate_tiles(self, max_level, min_level, dst_basedir):
		print 'From multi tiles'
		gen = TileTiler(
			self.map.height(), self.map.width(),
			self.src_dir,
			max_level, min_level,
			dst_basedir=dst_basedir, threads=self.threads)
		gen.set_out_extension(self.out_extension)
		gen.run()
	
class Map:
	def __init__(self, source, copyright_=None):
		self.source = source
		self.copyright = copyright_
		
		self.page_title = None
		# Consider mangling this pased on the image name
		self.id = 'si_canvas'
		self.out_dir = 'map'
		self.max_level = None
		self.min_level = 0
		self.image = None
		# don't error on missing tiles in grid
		self.skip_missing = False
		self.set_out_extension('.jpg')
		self.tw = 250
		self.th = 250
		
	def set_out_extension(self, s):
		self.out_extension = s
		self.source.out_extension = s
		self.out_format = s.replace('.', '')
		if self.out_format == 'png':
			self.is_png_str = 'isPng: true,'
		else:
			self.is_png_str = ''
	
	def header(self):
		return '''\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="application/xhtml+xml; charset=utf-8" />  
<title>%s</title>
<script type="text/javascript" src="https://maps.google.com/maps/api/js?sensor=false"></script>
<style type="text/css">
  html { height: 100%% }
  body { height: 100%%; margin: 0; padding: 0 }
  #%s { height: 100%% }
</style>

</head>
<body>
''' % (self.page_title, self.id);

	def get_js(self):
		ret = ''
		ret += self.header()
		ret += self.div()
		ret += self.script()
		ret += self.footer()
		return ret

	def div(self):
		return '''
<div id="%s"></div>
''' % self.id;

	def script(self):
		ret = ''
		ret += self.script_header()
		ret += self.SiProjection_ctor()
		ret += self.fromLatLngToPoint()
		ret += self.fromPointToLatLng()
		ret += self.create_map()
		ret += self.script_footer()
		return ret
		
	def width(self):
		return self.source.width()
	def height(self):
		return self.source.height()
		
	def SI_MAX_ZOOM(self):
		return self.max_level
		
	def SI_RANGE_X(self):
		return self.width() / (2**self.SI_MAX_ZOOM())
	
	def SI_RANGE_Y(self):
		return self.height() / (2**self.SI_MAX_ZOOM())
	
	def script_header(self):
			return '''
<script>
//WARNING: this page is automatically generated by pr0nmap
var options = {
  scrollwheel: true,
  //FIXME: look into
  //scaleControl: true,
  mapTypeControlOptions: {style: google.maps.MapTypeControlStyle.DROPDOWN_MENU},
  streetViewControl: false
}
''';

	def SiProjection_ctor(self):
		return '''
function SiProjection() {
  // Using the base map tile, denote the lat/lon of the equatorial origin.
  this.worldOrigin_ = new google.maps.Point(%d / 2, %d / 2);

  // This projection has equidistant meridians, so each longitude
  // degree is a linear mapping.
  this.worldCoordinatePerLonDegree_ = %d / 360;
  this.worldCoordinatePerLatDegree_ = %d / 360;
};
''' % (self.SI_RANGE_X(), self.SI_RANGE_Y(), self.SI_RANGE_X(), self.SI_RANGE_Y());

	def fromLatLngToPoint(self):
		return '''
firstL = false
//firstL = true
SiProjection.prototype.fromLatLngToPoint = function(latLng) {
	var origin = this.worldOrigin_;
	var x = origin.x + this.worldCoordinatePerLonDegree_ * latLng.lng();
	var y = origin.y + this.worldCoordinatePerLatDegree_ * latLng.lat();
	if (firstL) {
		firstL = false;
		alert('(lng ' + latLng.lng() + ', lat ' + latLng.lat() + ') => (x ' + x + ', y ' + y + ')')
	}
	return new google.maps.Point(x, y);
};
''';

	def fromPointToLatLng(self):
		return '''
SiProjection.prototype.fromPointToLatLng = function(point, noWrap) {
  var y = point.y;
  var x = point.x;

  if (x < 0) {
    x = 0;
  }
  if (x >= %d) {
    x = %d;
  }
  if (y < 0) {
    y = 0;
  }
  if (y >= %d) {
    y = %d;
  }
  
if (firstL) {
	firstL = false;
	alert('(x ' + x + ', y ' + y + ') => (lng ' + latLng.lng() + ', lat ' + latLng.lat() + ')')
}

  var origin = this.worldOrigin_;
  var lng = (x - origin.x) / this.worldCoordinatePerLonDegree_;
  var lat = (y - origin.y) / this.worldCoordinatePerLatDegree_;
  return new google.maps.LatLng(lat, lng, noWrap);
};
''' % (self.SI_RANGE_X(), self.SI_RANGE_X(), self.SI_RANGE_Y(), self.SI_RANGE_Y());

	def create_map(self):
		return ('''
var siMap = new google.maps.Map(document.getElementById("si_canvas"), options);
siMap.setCenter(new google.maps.LatLng(1, 1));
siMap.setZoom(%d);

first = false
//first = true;
var %s = new google.maps.ImageMapType({
  getTileUrl: function(ll, z) {
  	//TODO: consider not 0 padding if this is going to be a performance issue
  	//it does make organizing them easier though
    var r = "tiles_out/" + z + "/y" + String("00" + ll.y).slice(-3) + "_x" + String("00" + ll.x).slice(-3) + "%s"; 
	if (first) {
	    first = false;
	    alert(r);
    }
    return r;
  },
  format:"%s",
  tileSize: new google.maps.Size(''' + str(self.tw) + ', ' + str(self.th) + '''),
  %s
  maxZoom: %d,
  name: "SM",
  alt: "IC map"
});
''') % (self.min_level, self.type_obj_name(), self.out_extension, self.out_format, self.is_png_str, self.SI_MAX_ZOOM())

	def type_obj_name(self):
		#return 'mos6522NoMetal'
		return 'ICImageMapType'

	def map_type(self):
		#return 'mos6522'
		return 'ICImageMapType'

	def script_footer(self):
		ret = '''
%s.projection = new SiProjection();


siMap.mapTypes.set('%s', %s);
siMap.setMapTypeId('%s');
''' % (self.type_obj_name(), self.type_obj_name(), self.type_obj_name(), self.type_obj_name())
		if self.copyright:
			ret += '''
// Create div for showing copyrights.
var copyrightNode;
copyrightNode = document.createElement('div');
copyrightNode.id = 'copyright-control';
copyrightNode.style.fontSize = '11px';
copyrightNode.style.fontFamily = 'Arial, sans-serif';
copyrightNode.style.margin = '0 2px 2px 0';
copyrightNode.style.whiteSpace = 'nowrap';
copyrightNode.index = 0;
copyrightNode.innerHTML = "%s";
siMap.controls[google.maps.ControlPosition.BOTTOM_RIGHT].push(copyrightNode);
''' % self.copyright

		ret += '''
siMap.setOptions({
  mapTypeControlOptions: {
    mapTypeIds: [
      '%s'
    ],
    style: google.maps.MapTypeControlStyle.DROPDOWN_MENU,
  },
  streetViewControl: false
});


</script>
''' % (self.map_type(),)
		return ret

	def footer(self):
		return '''
</body>
</html>
''';

	def zoom_factor(self):
		return 2

	def calc_max_level(self):
		self.max_level = self.source.calc_max_level()

	def gen_js(self):
		if self.page_title is None:
			self.page_title = 'SiMap: %s' % self.source.get_name()
	
		# If it looks like there is old output and we are trying to re-generate js don't nuke it
		if os.path.exists(self.out_dir) and not self.js_only:
			os.system('rm -rf %s' % self.out_dir)
		if not os.path.exists(self.out_dir):
			os.mkdir(self.out_dir)

		if self.max_level is None:
			self.calc_max_level()
		js = self.get_js()
		js_filename = '%s/index.html' % self.out_dir
		print 'Writing javascript to %s' % js_filename
		open(js_filename, 'w').write(js)
		
		self.image = None

	def generate(self):
		'''
		It would be a good idea to check the tiles gnerated against what we are expecting
		'''
		# generate javascript
		self.gen_js()
		if not self.js_only:
			print
			print
			print
			self.source.generate_tiles(self.max_level, self.min_level, dst_basedir='%s/tiles_out' % self.out_dir)

