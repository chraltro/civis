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
  let prevTab = state.tab;

  const render = (): void => {
    syncHeaderFromState();
    syncTabsActive(tabsHost);
    const tabChanged = prevTab !== state.tab;
    prevTab = state.tab;

    const doRender = () => {
      if (state.tab === "overview" || !data.domains.includes(state.tab)) {
        renderOverview(content, data);
      } else {
        renderDomain(content, data, state.tab);
      }
      content.classList.remove("swapping");
    };

    if (tabChanged) {
      // Brief fade for the swap; also reset scroll so each tab opens at top.
      content.classList.add("swapping");
      window.setTimeout(() => {
        doRender();
        window.scrollTo({ top: 0, behavior: "auto" });
      }, 90);
    } else {
      doRender();
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
