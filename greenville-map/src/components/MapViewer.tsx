import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import L from "leaflet";

// Fix default marker icon paths (Vite bundles assets differently)
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";

L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

const DEFAULT_CENTER: [number, number] = [34.8526, -82.3940]; // Greenville, SC (lat, lon)

// Dynamic layer configuration based on available tables
type LayerConfig = { color: string; weight: number; fillOpacity: number };

// Default color palette for different layer types
const getDefaultLayerConfig = (layerName: string): LayerConfig => {
  const configs: Record<string, LayerConfig> = {
    parcels: { color: "#444", weight: 1, fillOpacity: 0 },
    zoning: { color: "#2b8cbe", weight: 1, fillOpacity: 0.25 },
    streets: { color: "#666", weight: 1.2, fillOpacity: 0 },
    parks: { color: "#2ca25f", weight: 1, fillOpacity: 0.3 },
    schools: { color: "#ff7f0e", weight: 1, fillOpacity: 0.3 },
    busstops: { color: "#d62728", weight: 1, fillOpacity: 0.6 },
    busroutes: { color: "#9467bd", weight: 2, fillOpacity: 0 },
    buildingfootprints: { color: "#8c564b", weight: 1, fillOpacity: 0.2 },
    citylimits: { color: "#e377c2", weight: 2, fillOpacity: 0 },
    citycouncildistricts: { color: "#17becf", weight: 2, fillOpacity: 0.1 },
    femafloodzones: { color: "#1f77b4", weight: 1, fillOpacity: 0.3 },
    trails: { color: "#ff7f0e", weight: 2, fillOpacity: 0 },
    sidewalks: { color: "#bcbd22", weight: 1, fillOpacity: 0 },
    railroads: { color: "#2ca02c", weight: 2, fillOpacity: 0 },
    riversandstreams: { color: "#1f77b4", weight: 2, fillOpacity: 0.4 },
    majorwaterbodies: { color: "#1f77b4", weight: 1, fillOpacity: 0.6 },
    specialemphasisneighborhoods: { color: "#ff9896", weight: 2, fillOpacity: 0.2 },
    edgeofpavement: { color: "#d62728", weight: 1, fillOpacity: 0 },
    bicycleinfrastructure: { color: "#2ca02c", weight: 2, fillOpacity: 0 },
    bicycleroutes: { color: "#2ca02c", weight: 3, fillOpacity: 0 },
    collegesanduniversities: { color: "#8c564b", weight: 1, fillOpacity: 0.4 },
    communityandrecreationcenters: { color: "#ff7f0e", weight: 1, fillOpacity: 0.4 },
    parking: { color: "#bcbd22", weight: 1, fillOpacity: 0.3 },
    trailsmilemarkers: { color: "#ff7f0e", weight: 1, fillOpacity: 0.8 },
    addresses: { color: "#d62728", weight: 1, fillOpacity: 0.8 },
  };
  
  return configs[layerName.toLowerCase()] || { color: "#666", weight: 1, fillOpacity: 0.2 };
};

type GeoJSONFeature = {
  type: "Feature";
  geometry: unknown;
  properties?: Record<string, unknown>;
};

type FeatureCollection = {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
};

type LoadedGeoMap = Record<string, FeatureCollection>;
type VisibleLayers = Record<string, boolean>;

export default function MapViewer() {
  const mapRef = useRef<L.Map | null>(null);
  const [availableTables, setAvailableTables] = useState<string[]>([]);
  const [loadedGeo, setLoadedGeo] = useState<LoadedGeoMap>({}); // { tableName: geojson }
  const [visible, setVisible] = useState<VisibleLayers>({});
  const [loading, setLoading] = useState(false);
  const [tablesLoading, setTablesLoading] = useState(true);
  // API base with simple fallback between localhost and 127.0.0.1
  const apiFromEnv = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined;
  const [API_BASE] = useState<string>(() => {
    if (apiFromEnv) return apiFromEnv;
    const preferLocalhost = window.location.hostname === "localhost";
    return preferLocalhost ? "http://localhost:8000" : "http://127.0.0.1:8000";
  });

  // Subdivision state
  const [subdivisions, setSubdivisions] = useState<FeatureCollection | null>(null);
  const [selectedYear, setSelectedYear] = useState<number>(2025);
  const [showSubdivisionTimeline, setShowSubdivisionTimeline] = useState<boolean>(false);

  // Fetch available tables from API
  async function fetchAvailableTables() {
    try {
      setTablesLoading(true);
      const res = await fetch(`${API_BASE}/tables`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const tables = data.tables.filter((table: string) => 
        !['geography_columns', 'geometry_columns', 'spatial_ref_sys', 'shapefile_imports'].includes(table)
      );
      setAvailableTables(tables);
      
      // Initialize visible layers - show parcels by default
      const initialVisible: VisibleLayers = {};
      tables.forEach((table: string) => {
        initialVisible[table] = table === 'parcels';
      });
      setVisible(initialVisible);
      
      // Preload parcels initially
      if (tables.includes('parcels')) {
        fetchLayer('parcels');
      }
    } catch (err) {
      console.error("Failed to fetch available tables:", err);
      const message = err instanceof Error ? err.message : String(err);
      alert(`Failed to fetch available tables: ${message}`);
    } finally {
      setTablesLoading(false);
    }
  }

  useEffect(() => {
    fetchAvailableTables();
    // eslint-disable-next-line
  }, []);

  // Fetch subdivisions GeoJSON and stats, then merge
  useEffect(() => {
    async function loadSubdivisions() {
      try {
        const [geoRes, statsRes] = await Promise.all([
          fetch(`${API_BASE}/geojson/subdivisions`),
          fetch(`${API_BASE}/subdivision_stats`),
        ]);
        if (!geoRes.ok) throw new Error(await geoRes.text());
        if (!statsRes.ok) throw new Error(await statsRes.text());
        const geo = (await geoRes.json()) as FeatureCollection;
        const stats = (await statsRes.json()) as Array<Record<string, any>>;

        const byName = new Map<string, Record<string, any>>();
        stats.forEach((s) => {
          const key = (s.subdiv ?? s.SUBDIV ?? s.Subdiv) as string;
          if (key) byName.set(key, s);
        });

        const merged: FeatureCollection = {
          type: "FeatureCollection",
          features: geo.features.map((f) => {
            const props = f.properties || {};
            const name = (props["subdivision"] ?? props["SUBDIV"] ?? props["Subdiv"]) as string;
            const stat = name ? byName.get(name) : undefined;
            const first_date = stat?.first_date ?? null;
            const parcel_count = stat?.parcel_count ?? null;
            const total_acres = stat?.total_acres ?? null;
            return {
              ...f,
              properties: {
                ...props,
                first_date,
                parcel_count,
                total_acres,
              },
            } as GeoJSONFeature;
          }),
        };
        setSubdivisions(merged);
      } catch (e) {
        console.error("Failed to load subdivisions:", e);
        const msg = e instanceof Error ? e.message : String(e);
        alert(`Failed to load subdivisions: ${msg}`);
      }
    }
    loadSubdivisions();
    // eslint-disable-next-line
  }, [API_BASE]);

  async function fetchLayer(table: string) {
    if (loadedGeo[table]) return; // cached
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/geojson/${table}?limit=9000`);
      if (!res.ok) throw new Error(await res.text());
      const json = (await res.json()) as FeatureCollection;
      setLoadedGeo((s) => ({ ...s, [table]: json }));
    } catch (err) {
      console.error("Failed to fetch", table, err);
      const message = err instanceof Error ? err.message : String(err);
      alert(`Failed to fetch ${table}: ${message}`);
    } finally {
      setLoading(false);
    }
  }

  function toggleLayer(table: string) {
    setVisible((s) => {
      const newS = { ...s, [table]: !s[table] };
      // if turning on, fetch if needed
      if (!loadedGeo[table] && !s[table]) fetchLayer(table);
      return newS;
    });
  }

  function onEachFeature(feature: GeoJSONFeature, layer: L.Layer) {
    const props = feature.properties || {};
    // show first 8 properties in popup
    const entries = Object.entries(props).slice(0, 8).map(([k, v]) => {
      return `<b>${k}</b>: ${String(v)}<br/>`;
    });
    if ("bindPopup" in layer && typeof (layer as any).bindPopup === "function") {
      (layer as any).bindPopup(`<div style="max-width:280px">${entries.join("")}</div>`);
    }
  }

  function styleForLayer(table: string) {
    const cfg = getDefaultLayerConfig(table);
    return () => cfg;
  }

  // Subdivision styling based on first_date year and slider
  function getSubdivisionStyleFactory(currentYear: number) {
    return (feature: any) => {
      const year = feature?.properties?.first_date
        ? new Date(feature.properties.first_date).getFullYear()
        : 9999;
      let color = "gray";
      if (year < 1950) color = "brown";
      else if (year < 1980) color = "orange";
      else if (year < 2000) color = "green";
      else color = "blue";
      const isFuture = year > currentYear;
      return { color, weight: 2, fillOpacity: isFuture ? 0.05 : 0.3 } as L.PathOptions;
    };
  }

  // Subdivision popup per feature
  function onEachSubdivisionFeature(feature: any, layer: L.Layer) {
    const p = feature?.properties || {};
    const html = `
      <div>
        <strong>${p.subdivision ?? "Unknown"}</strong><br />
        First Date: ${p.first_date ?? "-"}<br />
        Parcels: ${p.parcel_count ?? "-"}<br />
        Acres: ${p.total_acres ?? "-"}
      </div>
    `;
    if ("bindPopup" in layer && typeof (layer as any).bindPopup === "function") {
      (layer as any).bindPopup(html);
    }
  }

  // (Optional) export selected visible layers to a combined GeoJSON file
  function exportVisibleGeoJSON() {
    const features: GeoJSONFeature[] = [];
    Object.keys(visible).forEach((t) => {
      if (visible[t] && loadedGeo[t]?.features) {
        features.push(...loadedGeo[t]!.features);
      }
    });
    const fc: FeatureCollection = { type: "FeatureCollection", features };
    const blob = new Blob([JSON.stringify(fc)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "selected_layers.geojson";
    a.click();
    URL.revokeObjectURL(url);
  }

  function MapRefSetter() {
    const map = useMap();
    useEffect(() => {
      mapRef.current = map as L.Map;
      // Ensure a dedicated pane for subdivisions sits above other overlays
      const paneName = "subdivisions-pane";
      if (!map.getPane(paneName)) {
        const pane = map.createPane(paneName);
        pane.style.zIndex = "650"; // higher than default overlayPane (~400-600)
        pane.style.pointerEvents = "auto";
      }
    }, [map]);
    return null;
  }

  return (
    <div style={{ height: "100%", width: "100%", position: "relative" }}>
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={13}
        style={{ height: "100vh", width: "100vw" }}
      >
        <MapRefSetter />
        <TileLayer
          attribution='© OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {Object.keys(visible).map((table) =>
          visible[table] && loadedGeo[table]?.features ? (
            <GeoJSON
              key={table}
              data={loadedGeo[table]! as unknown as any}
              style={styleForLayer(table)}
              onEachFeature={onEachFeature}
            />
          ) : null
        )}

        {/* Subdivisions filtered by time slider (render AFTER others + in own pane) */}
        {showSubdivisionTimeline && subdivisions && (
          <GeoJSON
            key={`subdivisions-${selectedYear}-${subdivisions.features.length}`}
            pane="subdivisions-pane"
            data={{
              type: "FeatureCollection",
              features: subdivisions.features.filter((f) => {
                const fd = (f.properties as any)?.first_date;
                if (!fd) return true; // keep if no date, show dimmed by style
                const y = new Date(fd).getFullYear();
                return y <= selectedYear;
              }) as any,
            } as any}
            style={getSubdivisionStyleFactory(selectedYear) as any}
            onEachFeature={onEachSubdivisionFeature as any}
          />
        )}
      </MapContainer>

      {/* UI controls */}
      <div style={{
        position: "absolute",
        top: 12,
        right: 12,
        background: "green",
        padding: 16,
        borderRadius: 8,
        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
        zIndex: 1000,
        minWidth: 280,
        maxHeight: "80vh",
        overflowY: "auto"
      }}>
        <div style={{ fontWeight: 700, marginBottom: 12, fontSize: 16 }}>Available Layers</div>
        {tablesLoading ? (
          <div style={{ color: "#666", fontStyle: "italic" }}>Loading layers...</div>
        ) : (
          <>
            <div style={{ marginBottom: 12, fontSize: 12, color: "#666" }}>
              {availableTables.length} layers available
            </div>
            {availableTables.map((table) => (
              <label key={table} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <input
                  type="checkbox"
                  checked={visible[table] || false}
                  onChange={() => toggleLayer(table)}
                />
                <span style={{ 
                  width: 12, 
                  height: 12, 
                  background: getDefaultLayerConfig(table).color, 
                  display: "inline-block", 
                  borderRadius: 2,
                  border: "1px solid #ccc"
                }} />
                <span style={{ 
                  textTransform: "capitalize",
                  fontSize: 14,
                  flex: 1
                }}>
                  {table.replace(/([A-Z])/g, ' $1').trim()}
                </span>
              </label>
            ))}
          </>
        )}

        <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
          <button onClick={() => exportVisibleGeoJSON()} style={{ flex: 1 }}>
            Export visible
          </button>
          <button onClick={() => {
            if (mapRef.current) {
              mapRef.current.setView(DEFAULT_CENTER, 13);
            }
          }}>
            Reset
          </button>
        </div>

        {/* Toggle + Time slider for subdivisions */}
        <div style={{ marginTop: 12 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={showSubdivisionTimeline}
              onChange={() => setShowSubdivisionTimeline((v) => !v)}
            />
            <span style={{ fontWeight: 600 }}>Enable Subdivision Timeline</span>
          </label>
          {showSubdivisionTimeline && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>Subdivision Timeline</div>
              <input
                type="range"
                min={1900}
                max={2025}
                value={selectedYear}
                onChange={(e) => setSelectedYear(Number(e.target.value))}
                style={{ width: "100%" }}
              />
              <div style={{ fontSize: 12, color: "#333", marginTop: 4 }}>Year: {selectedYear}</div>
            </div>
          )}
        </div>

        <div style={{ marginTop: 12, fontSize: 12, color: "#666", borderTop: "1px solid #eee", paddingTop: 8 }}>
          {loading ? "Loading layer data..." : "Click features for details. Use Export to download visible layers."}
        </div>
      </div>
    </div>
  );
}
