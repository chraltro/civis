/**
 * Civis Index dashboard — entry point.
 *
 * Loads civis.json, wires up state/controls, renders charts,
 * subscribes to state changes for incremental redraw.
 */

import { drawBar } from "./charts/bar";
import { drawPanels } from "./charts/panel";
import { drawRadar } from "./charts/radar";
import { drawTimeSeries } from "./charts/timeseries";
import { computeComposite, initWeights, subscribe } from "./state";
import { buildControls, updateControlsFromState } from "./ui/controls";
import { buildMethod, buildFooter } from "./ui/method";
import { buildWeightSliders } from "./ui/weights";
import { loadData, nameMap, type CivisData } from "./data";

async function bootstrap(): Promise<void> {
  const data = await loadData();
  if (!data) {
    document.getElementById("empty-state")?.removeAttribute("hidden");
    return;
  }
  document.getElementById("dashboard")?.removeAttribute("hidden");

  initWeights(data.domains);
  // expose name map for ui/controls
  (window as unknown as { __civisNames?: Record<string, string> }).__civisNames = nameMap(data);

  buildMethod(data);
  buildFooter(data);
  buildControls(data);
  buildWeightSliders(data.domains);

  const redraw = () => {
    const ctx = computeComposite(data);
    updateControlsFromState();
    drawBar(data, ctx);
    drawTimeSeries(data, ctx);
    drawRadar(data, ctx);
    drawPanels(data);
  };

  subscribe(redraw);
  redraw();

  // re-render on viewport bucket change
  let lastBucket = window.innerWidth < 600 ? "m" : "d";
  window.addEventListener("resize", () => {
    const bucket = window.innerWidth < 600 ? "m" : "d";
    if (bucket !== lastBucket) {
      lastBucket = bucket;
      redraw();
    }
  });
  // silence unused var
  void (data as CivisData);
}

bootstrap();
