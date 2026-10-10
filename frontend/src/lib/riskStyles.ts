import type { PathOptions } from "leaflet";
import type { Risk } from "../types/api";

export interface RiskStyle {
  labelKey: string;
  marker: string;
  pathOptions: PathOptions;
}

export const riskStyles: Record<Risk, RiskStyle> = {
  normal: {
    labelKey: "risk.normal",
    marker: "●",
    pathOptions: {
      color: "#236744",
      fillColor: "#58a878",
      fillOpacity: 0.48,
      weight: 2
    }
  },
  watch: {
    labelKey: "risk.watch",
    marker: "◒",
    pathOptions: {
      color: "#855a0b",
      dashArray: "7 4",
      fillColor: "#d8aa4a",
      fillOpacity: 0.5,
      weight: 2
    }
  },
  alert: {
    labelKey: "risk.alert",
    marker: "▲",
    pathOptions: {
      color: "#a62c28",
      dashArray: "2 3",
      fillColor: "#dd766c",
      fillOpacity: 0.55,
      weight: 3
    }
  },
  cannot_assess: {
    labelKey: "risk.cannot_assess",
    marker: "◩",
    pathOptions: {
      color: "#48586a",
      dashArray: "5 5",
      fillColor: "url(#risk-hatch-cannot-assess)",
      fillOpacity: 0.82,
      weight: 2
    }
  }
};
