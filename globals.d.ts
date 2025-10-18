declare var OSM_URL: string;
declare var OSRM_URL: string;

interface Waypoint {
    latlng: L.LatLng;
    name: string;
}

interface ServerCoordinate {
    lat: number;
    lng: number;
}

interface ServerWaypoint extends ServerCoordinate {
    name: string;
}

interface TwistGeometryData {
    name: string;
    is_paved: boolean;
    waypoints: ServerWaypoint[];
    route_geometry: ServerCoordinate[];
}

// Hacky way to get leaflet type checking
declare namespace L {

    // --- Basic Types ---
    type LatLng = { lat: number, lng: number };
    type Map = any; 
    type Marker = any;
    type Polyline = any;
    type TileLayer = any;
    type FeatureGroup = any;

    // --- Classes ---
    class Icon {
        constructor(options: object);
    }

    // --- Functions on L ---
    function map(id: string | HTMLElement, options?: object): Map;
    function marker(latlng: LatLng, options?: object): Marker;
    function polyline(latlngs: LatLng[], options?: object): Polyline;
    function icon(options: object): Icon;
    function tileLayer(urlTemplate: string, options?: object): TileLayer;
    function featureGroup(layers?: any[]): FeatureGroup;
}

declare var htmx: any;