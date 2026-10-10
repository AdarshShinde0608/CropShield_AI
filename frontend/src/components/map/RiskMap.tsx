import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Polygon, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { LeafletMouseEvent, PathOptions, Polygon as LeafletPolygon } from "leaflet";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import MapLegend from "./MapLegend";
import MapViewport from "./MapViewport";
import { riskStyles } from "../../lib/riskStyles";
import type { FieldFeature, FieldCollection } from "../../types/api";

type BaseLayer = "street" | "satellite";

interface RiskMapProps {
  fields: FieldCollection;
  selectedFieldId?: string | null;
  onSelectField?: (fieldId: string | null) => void;
  className?: string;
}

const baseLayers: Record<BaseLayer, { url: string; attribution: string }> = {
  street: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  },
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
  }
};

export default function RiskMap({
  fields,
  selectedFieldId,
  onSelectField,
  className = ""
}: RiskMapProps) {
  const { t } = useTranslation();
  const [internalSelected, setInternalSelected] = useState<string | null>(null);
  const [baseLayer, setBaseLayer] = useState<BaseLayer>("street");
  const selectedId = selectedFieldId === undefined ? internalSelected : selectedFieldId;
  const select = useCallback((fieldId: string | null) => {
    setInternalSelected(fieldId);
    onSelectField?.(fieldId);
  }, [onSelectField]);
  const firstCoordinates = fields.features[0]?.geometry.coordinates[0]?.[0];
  const center: [number, number] = firstCoordinates
    ? [firstCoordinates[1], firstCoordinates[0]]
    : [19, 73];

  return (
    <section aria-label={t("map.ariaLabel")} className={`min-w-0 ${className}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <MapLegend />
        <div aria-label={t("map.baseLayer")} className="inline-flex rounded-lg border border-stone-200 bg-white p-1" role="group">
          {(["street", "satellite"] as const).map((layer) => (
            <button
              aria-pressed={baseLayer === layer}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold ${baseLayer === layer ? "bg-brand-700 text-white" : "text-slate-700 hover:bg-stone-100"}`}
              key={layer}
              onClick={() => setBaseLayer(layer)}
              type="button"
            >
              {t(`map.${layer}`)}
            </button>
          ))}
        </div>
      </div>
      <MapContainer
        center={center}
        className="h-[min(62vh,560px)] min-h-[340px] w-full rounded-2xl bg-slate-100"
        scrollWheelZoom
        zoom={14}
      >
        <TileLayer attribution={baseLayers[baseLayer].attribution} url={baseLayers[baseLayer].url} />
        <MapViewport fields={fields} />
        {fields.features.map((feature) => (
          <FieldPolygon
            feature={feature}
            key={feature.properties.field_id}
            onSelect={select}
            selected={feature.properties.field_id === selectedId}
          />
        ))}
        <MapSelection selectedId={selectedId} onClear={() => select(null)} />
      </MapContainer>
      <p className="sr-only" aria-live="polite">
        {selectedId ? t("map.fieldSelected", { field: selectedId }) : ""}
      </p>
    </section>
  );
}

function FieldPolygon({
  feature,
  selected,
  onSelect
}: {
  feature: FieldFeature;
  selected: boolean;
  onSelect: (fieldId: string) => void;
}) {
  const { t } = useTranslation();
  const field = feature.properties;
  const riskStyle = riskStyles[field.risk];
  const ring = feature.geometry.coordinates[0] ?? [];
  const positions = useMemo(
    () => ring.map(([longitude, latitude]) => [latitude, longitude] as [number, number]),
    [ring]
  );
  const center = useMemo<[number, number]>(() => {
    const points = ring.slice(0, -1);
    if (!points.length) return [0, 0];
    const totals = points.reduce(
      (sum, [longitude, latitude]) => [sum[0] + latitude, sum[1] + longitude],
      [0, 0]
    );
    return [totals[0] / points.length, totals[1] / points.length];
  }, [ring]);
  const options = useMemo<PathOptions>(() => ({
    ...riskStyle.pathOptions,
    color: selected ? "#17251b" : riskStyle.pathOptions.color,
    weight: selected ? 4 : riskStyle.pathOptions.weight
  }), [riskStyle, selected]);
  const polygonRef = useRef<LeafletPolygon | null>(null);
  useEffect(() => {
    const path = polygonRef.current?.getElement();
    path?.setAttribute("role", "button");
    path?.setAttribute("tabindex", "0");
    path?.setAttribute("aria-label", t("map.fieldDescription", {
      field: field.name ?? field.field_id,
      risk: t(riskStyle.labelKey)
    }));
  }, [field.field_id, field.name, riskStyle.labelKey, t]);
  const openPopup = useCallback((event: LeafletMouseEvent) => {
    onSelect(field.field_id);
    event.target.openPopup();
  }, [field.field_id, onSelect]);

  return (
    <Polygon eventHandlers={{ click: openPopup }} pathOptions={options} positions={positions} ref={polygonRef}>
      <Tooltip direction="top" sticky>
        <span className="font-semibold">{field.name ?? field.field_id}</span>
        <span className="ml-2">{riskStyle.marker} {t(riskStyle.labelKey)}</span>
      </Tooltip>
      <Popup>
        <div className="min-w-40 space-y-2">
          <h3 className="font-bold text-slate-900">{field.name ?? field.field_id}</h3>
          <p className="text-sm text-slate-700">
            <span aria-hidden="true" className="mr-1">{riskStyle.marker}</span>
            {t(riskStyle.labelKey)}
          </p>
          <Link
            className="inline-flex rounded-lg bg-brand-700 px-3 py-2 text-sm font-bold text-white hover:bg-brand-800"
            onClick={() => onSelect(field.field_id)}
            to={`/fields/${encodeURIComponent(field.field_id)}`}
          >
            {t("map.viewDetails")}
          </Link>
        </div>
      </Popup>
      <SelectedFieldFocus selected={selected} center={center} />
    </Polygon>
  );
}

function SelectedFieldFocus({ selected, center }: { selected: boolean; center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    if (selected) map.panTo(center, { animate: false });
  }, [center, map, selected]);
  return null;
}

function MapSelection({ selectedId, onClear }: { selectedId: string | null; onClear: () => void }) {
  const map = useMap();
  const { t } = useTranslation();
  if (!selectedId) return null;
  return (
    <button
      aria-label={t("map.clearSelection")}
      className="absolute right-3 top-16 z-[1000] rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow"
      onClick={() => {
        onClear();
        map.closePopup();
      }}
      type="button"
    >
      {t("map.clearSelection")}
    </button>
  );
}
