// React import not needed with react-jsx runtime
import MapViewer from "./components/MapViewer.tsx";

export default function App() {
  return (
    <div className="app-root" style={{ height: "100vh", width: "100vw" }}>
      <MapViewer />
    </div>
  );
}
