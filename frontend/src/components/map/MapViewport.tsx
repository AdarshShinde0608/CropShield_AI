import { useEffect } from "react";
import { useMap } from "react-leaflet";
import type { FieldCollection } from "../../types/api";

export default function MapViewport({ fields }: { fields: FieldCollection }) {
  const map = useMap();

  useEffect(() => {
    const points = fields.features.flatMap((feature) =>
      feature.geometry.coordinates.flatMap((ring) =>
        ring.map(([longitude, latitude]) => [latitude, longitude] as [number, number])
      )
    );
    if (points.length) map.fitBounds(points, { padding: [28, 28], maxZoom: 16 });
  }, [fields, map]);

  useEffect(() => {
    let frame = 0;
    const addPattern = () => {
      const svg = map.getPanes().overlayPane.querySelector("svg");
      if (!svg) {
        frame = window.requestAnimationFrame(addPattern);
        return;
      }
      if (svg.querySelector("#risk-hatch-cannot-assess")) return;
      const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
      const pattern = document.createElementNS("http://www.w3.org/2000/svg", "pattern");
      pattern.setAttribute("id", "risk-hatch-cannot-assess");
      pattern.setAttribute("patternUnits", "userSpaceOnUse");
      pattern.setAttribute("width", "9");
      pattern.setAttribute("height", "9");
      pattern.setAttribute("patternTransform", "rotate(35)");
      const background = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      background.setAttribute("width", "9");
      background.setAttribute("height", "9");
      background.setAttribute("fill", "#e2e8f0");
      const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
      line.setAttribute("d", "M 0 0 L 0 9");
      line.setAttribute("stroke", "#64748b");
      line.setAttribute("stroke-width", "3");
      pattern.append(background, line);
      defs.append(pattern);
      svg.prepend(defs);
    };
    frame = window.requestAnimationFrame(addPattern);
    return () => window.cancelAnimationFrame(frame);
  }, [map]);

  return null;
}
