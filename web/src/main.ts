/** Civis Index — entry point. */

import { loadData, type CivisData } from "./data";
import { initRouter } from "./router";
import { initWeights, state, subscribe } from "./state";
import { buildAboutPanel } from "./ui/about";
import { buildHeader, syncHeaderFromState } from "./ui/header";
import { buildTabs, syncTabsActive } from "./ui/tabs";
import { buildWeightSliders } from "./ui/weights";
import { renderDomain } from "./views/domain";
import { renderOverview } from "./views/overview";

async function bootstrap(): Promise<void> {
  const data = await loadData();
  if (!data) {
    document.getElementById("empty-state")?.removeAttribute("hidden");
    return;
  }
  document.getElementById("content")?.removeAttribute("hidden");

  initWeights(data.domains);
  buildHeader(data);
  buildAboutPanel(data);
  buildWeightSliders(data.domains);
  const tabsHost = document.getElementById("tabs")!;
  buildTabs(tabsHost, data.domains);
  initRouter(data.domains);

  const stamp = document.getElementById("data-stamp");
  if (stamp) stamp.textContent = `data ${data.generated_at.slice(0, 10)}`;

  const content = document.getElementById("content")!;

  const render = (): void => {
    syncHeaderFromState();
    syncTabsActive(tabsHost);
    if (state.tab === "overview" || !data.domains.includes(state.tab)) {
      renderOverview(content, data);
    } else {
      renderDomain(content, data, state.tab);
    }
  };

  subscribe(render);
  render();

  // Re-render on viewport bucket change (mobile vs desktop chart sizes)
  let lastBucket = window.innerWidth < 600 ? "m" : "d";
  window.addEventListener("resize", () => {
    const bucket = window.innerWidth < 600 ? "m" : "d";
    if (bucket !== lastBucket) {
      lastBucket = bucket;
      render();
    }
  });
  void (data as CivisData);
}

bootstrap();
