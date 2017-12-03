import xml.etree.cElementTree as etree
import inspect, importlib

def prepareHandlers(kwArgs):
	nodeHandlers = []
	wayHandlers = []
	# getting a dictionary with local variables
	_locals = locals()
	for handlers in ("nodeHandlers", "wayHandlers"):
		if handlers in kwArgs:
			for handler in kwArgs[handlers]:
				if isinstance(handler, str):
					# we've got a module name
					handler = importlib.import_module(handler)
				if inspect.ismodule(handler):
					# iterate through all module functions
					for f in inspect.getmembers(handler, inspect.isclass):
						_locals[handlers].append(f[1])
				elif inspect.isclass(handler):
					_locals[handlers].append(handler)
		if len(_locals[handlers])==0: _locals[handlers] = None
	return (nodeHandlers if len(nodeHandlers) else None, wayHandlers if len(wayHandlers) else None)

class OsmParser:
	
	def __init__(self, filename, **kwargs):
		self.nodes = {}
		self.ways = {}
		self.relations = {}
		self.minLat = 90
		self.maxLat = -90
		self.minLon = 180
		self.maxLon = -180
		# self.bounds contains the attributes of the bounds tag of the .osm file if available
		self.bounds = None
		
		(self.nodeHandlers, self.wayHandlers) = prepareHandlers(kwargs)
		
		self.doc = etree.parse(filename)
		self.osm = self.doc.getroot()
		self.prepare()

	def prepare(self):
		allowedTags = set(("node", "way", "bounds"))
		for e in self.osm: # e stands for element
			attrs = e.attrib
			if e.tag not in allowedTags : continue
			if "action" in attrs and attrs["action"] == "delete": continue
			if e.tag == "node":
				_id = attrs["id"]
				tags = None
				for c in e:
					if c.tag == "tag":
						if not tags: tags = {}
						tags[c.get("k")] = c.get("v")
				lat = float(attrs["lat"])
				lon = float(attrs["lon"])
				# calculating minLat, maxLat, minLon, maxLon
				# commented out: only imported objects take part in the extent calculation
				#if lat<self.minLat: self.minLat = lat
				#elif lat>self.maxLat: self.maxLat = lat
				#if lon<self.minLon: self.minLon = lon
				#elif lon>self.maxLon: self.maxLon = lon
				# creating entry
				entry = dict(
					id=_id,
					e=e,
					lat=lat,
					lon=lon
				)
				if tags: entry["tags"] = tags
				self.nodes[_id] = entry
			elif e.tag == "way":
				_id = attrs["id"]
				nodes = []
				tags = None
				for c in e:
					if c.tag == "nd":
						nodes.append(c.get("ref"))
					elif c.tag == "tag":
						if not tags: tags = {}
						tags[c.get("k")] = c.get("v")
				# ignore ways without tags
				if tags:
					self.ways[_id] = dict(
						id=_id,
						e=e,
						nodes=nodes,
						tags=tags
					)
			elif e.tag == "bounds":
				self.bounds = {
					"minLat": float(attrs["minlat"]),
					"minLon": float(attrs["minlon"]),
					"maxLat": float(attrs["maxlat"]),
					"maxLon": float(attrs["maxlon"])
				}
		
		self.calculateExtent()

	def iterate(self, wayFunction, nodeFunction):
		nodeHandlers = self.nodeHandlers
		wayHandlers = self.wayHandlers
		
		if wayHandlers:
			for _id in self.ways:
				way = self.ways[_id]
				if "tags" in way:
					for handler in wayHandlers:
						if handler.condition(way["tags"], way):
							wayFunction(way, handler)
							continue
		
		if nodeHandlers:
			for _id in self.nodes:
				node = self.nodes[_id]
				if "tags" in node:
					for handler in nodeHandlers:
						if handler.condition(node["tags"], node):
							nodeFunction(node, handler)
							continue

	def parse(self, **kwargs):
		def wayFunction(way, handler):
			handler.handler(way, self, kwargs)
		def nodeFunction(node, handler):
			handler.handler(node, self, kwargs)
		self.iterate(wayFunction, nodeFunction)

	def calculateExtent(self):
		def wayFunction(way, handler):
			wayNodes = way["nodes"]
			for node in range(len(wayNodes)-1): # skip the last node which is the same as the first ones
				nodeFunction(self.nodes[wayNodes[node]])
		def nodeFunction(node, handler=None):
			lon = node["lon"]
			lat = node["lat"]
			if lat<self.minLat: self.minLat = lat
			elif lat>self.maxLat: self.maxLat = lat
			if lon<self.minLon: self.minLon = lon
			elif lon>self.maxLon: self.maxLon = lon
		self.iterate(wayFunction, nodeFunction)