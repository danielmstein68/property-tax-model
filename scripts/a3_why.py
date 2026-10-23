"""The "Why it works" page of the Amendment 3 artifact: markup and script, used by scripts/build_a3.py.

Evidence numbers come from inputs/fl_validation_evidence.yaml (check scripts that print), the grid's static Amendment 3
runs (the model), the state's estimate (inputs/fl_rec_amendment3.yaml) and the 2026 homestead check (fl_2026_validation.json).
"""

WHY_HTML = '''  <div id="view-why" class="wrap-inner" hidden>
    <section>
      <div class="eyebrow">How to read this page</div>
      <h2>Fitting is not checking</h2>
      <p>We fit the model to some sources and checked it against others. Where we set the model to match a source (home values, homestead counts and exemptions match the 2026 property rolls area by area), the match is guaranteed and shows nothing. Only a comparison with something the model was not set to match is evidence. This page leads with those, then lists what we cannot test.</p>
    </section>

    <section>
      <div class="eyebrow">Check 1 · Amendment 3's cost</div>
      <h2 id="why-h1"></h2>
      <p id="why-p1"></p>
      <div class="chart">
        <h3 id="why-h-bars"></h3>
        <p>Revenue lost to local governments each roll year, billions of dollars, with rates unchanged and no behavioural responses (the state's way of scoring).</p>
        <div id="why-c-bars"></div>
        <div class="legend"><span><i style="background:var(--gain1)"></i>Rebuilt from the property rolls alone</span><span><i style="background:var(--accent)"></i>This model</span><span><i style="background:var(--neutral)"></i>The state's estimate</span></div>
      </div>
      <div class="tablebox"><table id="why-t-pieces"></table></div>
      <p id="why-p1b"></p>
    </section>

    <section>
      <div class="eyebrow">Check 2 · The starting point</div>
      <h2>The 2026 baseline matches the property rolls and the state's forecast</h2>
      <p>Each homestead on the 2026 rolls was compared with the model's owners on the same 2025 tax rates. The comparison is by group; the model does not claim to get any one household right.</p>
      <div class="tablebox"><table id="why-t-base" class="wrap-cells"></table></div>
    </section>

    <section>
      <div class="eyebrow">Check 3 · How governments set rates</div>
      <h2 id="why-h3"></h2>
      <p id="why-p3"></p>
      <div class="chart">
        <h3 id="why-h-cov"></h3>
        <p>Share of actual county, city and school district rate changes that fell inside the rule's central 80% band, by period; a calibrated rule scores 80%.</p>
        <div id="why-c-cov"></div>
        <div class="legend"><span><i style="background:var(--accent)"></i>Inside the 80% band</span><span><i style="background:var(--rule-strong)"></i>Target: 80%</span></div>
      </div>
    </section>

    <section>
      <div class="eyebrow">Check 4 · An independent study</div>
      <h2 id="why-h4"></h2>
      <p id="why-p4"></p>
      <div class="tablebox"><table id="why-t-walczak" class="wrap-cells"></table></div>
    </section>

    <section>
      <div class="eyebrow">What we cannot test</div>
      <h2>Where the evidence runs out</h2>
      <ul class="about-list">
        <li><b>How many owners start claiming a bigger exemption.</b> Texas's 2024 claims put it anywhere from near zero to about a third of non-claiming owners, depending on the trend assumed; Florida's 2008 data is tangled up with the housing crash. The page uses 30% inside a 10% to 40% range. It moves the 2027 loss by about 2%.</li>
        <li><b>How local governments will react to a loss this large.</b> The rule predicts ordinary years well, but Florida has no precedent for a state-imposed loss of about 8% of all property tax. The page shows "rates unchanged" and "replace what they can" as bounds.</li>
        <li><b>Revenue after 2031.</b> The state publishes no estimate past 2031, and a back-test of the projections needs the 2025 rolls, which the Department of Revenue provides on request.</li>
        <li><b>Who gains, by income.</b> Modelled tax is within 5% to 8% of what households report in nine of ten income groups, but matching a household's income to its home is statistical. The pattern is reliable; the exact shares are not.</li>
        <li><b>Rents.</b> What renters pay through rent is not modelled.</li>
      </ul>
    </section>

    <section>
      <div class="eyebrow">Sources</div>
      <h2>Where the checks come from</h2>
      <ul class="about-list">
        <li><a href="https://edr.state.fl.us/Content/conferences/revenueimpact/archives/2026F/_pdf/impact0710.pdf">Revenue Estimating Conference, Amendment 3 impact (July 10, 2026)</a></li>
        <li>Florida Department of Revenue, 2026 parcel rolls (all 67 counties) and 2025 millage tables</li>
        <li>Jared Walczak, "Amendment 3 Could Shift Tax Burdens to Renters", Walczak Policy, September 2026</li>
        <li>Office of Economic and Demographic Research, ad valorem tax profiles, 1996-2025 (rate history)</li>
        <li>Check scripts and notes in the model's repository: <code>docs/checks/a3_vs_rec_gap.md</code>, <code>rate_history_backtest.md</code>, <code>takeup_checks.md</code></li>
      </ul>
    </section>
  </div>

'''

WHY_JS = r'''
const EV = __EVID__;   // inputs/fl_validation_evidence.yaml + the grid's static Amendment 3 runs + the state's estimate
(function () {
  const yrs = EV.years, B = v => "$" + v.toLocaleString("en-US", { minimumFractionDigits: v < 1 ? 2 : 1, maximumFractionDigits: v < 1 ? 2 : 1 }) + "B", pc = v => (100 * v).toFixed(0) + "%";
  const rolls = yrs.map((y, i) => EV.rolls_exempt[i] + EV.rolls_cap[i]);
  const gap = yrs.map((y, i) => EV.model_total[i] / rolls[i] - 1), worst = Math.max(...gap.map(Math.abs));
  const stateGap = yrs.map((y, i) => EV.model_total[i] / EV.state[i] - 1);
  $("why-h1").textContent = `Amendment 3's cost rebuilds from the property rolls to within ${Math.ceil(100 * worst)}%`;
  $("why-p1").textContent = "We took every homestead parcel on the 2026 rolls (5.2 million) and replaced its non-school exemption with the amendment's: $150,000 in 2027, $250,000 from 2028, indexed after. We took every other non-agricultural parcel and capped its yearly assessed-value growth at 5% instead of 10%. Each parcel's tax change uses its own district's 2025 rate. No survey, no households and no model are involved, so this is a separate calculation, and it lands on the model's answer in every year.";
  $("why-h-bars").textContent = `The model and the rolls agree to within ${Math.ceil(100 * worst)}%; the state's estimate is higher, by ${pc(-stateGap[0])} in ${yrs[0]} and ${pc(-stateGap[4])} by ${yrs[4]}`;

  // grouped bars: rolls-only, model, state, per year
  (function () {
    const series = [[rolls, "var(--gain1)"], [EV.model_total, "var(--accent)"], [EV.state, "var(--neutral)"]];
    const W = 620, H = 300, L = 52, R_ = 10, T = 20, Bm = 28, bw = (W - L - R_) / yrs.length, max = Math.ceil(Math.max(...EV.state) / 2) * 2;
    const s = svg(W, H), yy = v => T + (H - T - Bm) * (1 - v / max);
    s.setAttribute("aria-label", "Amendment 3 revenue lost by year: rebuilt from the property rolls, the model, and the state's estimate");
    for (let v = 0; v <= max; v += 2) { el(s, "line", { x1: L, x2: W - R_, y1: yy(v), y2: yy(v), stroke: "var(--rule)" }); el(s, "text", { x: L - 6, y: yy(v) + 4, "text-anchor": "end" }, "$" + v + "B"); }
    yrs.forEach((y, i) => {
      series.forEach(([arr, c], j) => { const x = L + i * bw + bw * 0.1 + j * bw * 0.27, w = bw * 0.24;
        el(s, "rect", { x, y: yy(arr[i]), width: w, height: yy(0) - yy(arr[i]), fill: c, rx: 2 });
        el(s, "text", { x: x + w / 2, y: yy(arr[i]) - 4, "text-anchor": "middle", class: "val" }, arr[i].toFixed(1)); });
      el(s, "text", { x: L + i * bw + bw / 2, y: H - 8, "text-anchor": "middle" }, String(y)); });
    $("why-c-bars").innerHTML = ""; $("why-c-bars").appendChild(s);
  })();

  $("why-t-pieces").innerHTML = `<thead><tr><th>Billions of dollars</th>${yrs.map(y => `<th>${y}</th>`).join("")}</tr></thead><tbody>` +
    [["Larger exemption: rebuilt from the rolls", EV.rolls_exempt], ["Larger exemption: this model", EV.model_exempt],
     ["5% cap: rebuilt from the rolls", EV.rolls_cap], ["5% cap: this model", EV.model_cap],
     ["Total: rebuilt from the rolls", rolls], ["Total: this model", EV.model_total], ["Total: the state's estimate", EV.state]]
    .map(([l, a]) => `<tr><td>${l}</td>${a.map(v => `<td>${v.toFixed(2)}</td>`).join("")}</tr>`).join("") + "</tbody>";
  $("why-p1b").innerHTML = `<b>Why the state's number is higher.</b> The state scales its parcel-level result each year up to its own forecast of taxable value: by ${EV.scale[0].toFixed(2)} times in ${yrs[0]}, ${EV.scale[4].toFixed(2)} times by ${yrs[4]} for homesteads. That treats every dollar of value growth beyond the Save Our Homes cap, including sales and new construction, as more homesteads. Applying the same scale to the model closes the 2031 gap from ${pc(-stateGap[4])} to ${pc(-(EV.model_total[4] * EV.scale[4] / EV.state[4] - 1))}. We cannot tell from published data which treatment is closer for the later years, so the results page is scaled to the state's figures and says so.`;

  // 2) baseline table
  const V = VAL;
  $("why-t-base").innerHTML = "<thead><tr><th>What's compared</th><th>This model</th><th>The other source</th></tr></thead><tbody>" + [
    ["Homestead taxable value, county and city taxes", B(V.nonschool_taxable_model / 1e9), `${B(V.nonschool_taxable_roll / 1e9)} (parcel rolls)`],
    ["Average homestead tax", usd(V.avg_tax_model), `${usd(V.avg_tax_roll)} (parcel rolls)`],
    ["Median homestead tax", usd(V.median_tax_model), `${usd(V.median_tax_roll)} (parcel rolls)`],
    ["County government tax paid by homesteads, 66 counties", "1.05 times official", "Official levies times homestead share"],
    ["Statewide taxable value, 2026", "$3,965B school, $3,673B county", "$3,966B, $3,673B (Revenue Estimating Conference)"],
    ["Projected taxable value, 2031", "School 0.6% and county 1.9% above", "Revenue Estimating Conference, August 2026"],
    ["Tax owners report in the survey, by income tenth", `${Math.min(...EV.ratio_by_decile).toFixed(2)} to ${Math.max(...EV.ratio_by_decile).toFixed(2)} times reported`, "Census survey, 2024 (reported tax includes reporting error)"],
  ].map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("") + "</tbody>";

  // 3) rate back-test
  $("why-h3").textContent = `The rate-setting rule is right about as often as it says: ${pc(EV.inside_80.all)} of ${EV.n.toLocaleString("en-US")} actual rate changes fell inside its 80% band`;
  $("why-p3").textContent = "The model draws each government's rate change from what Florida governments did in years with similar growth in their tax base. To test it, we fitted the rule on years before each test year from 2006 on and asked it to predict every county, city and school district rate change in that year. It holds for counties, cities and school districts and through the 2008 to 2012 downturn. The one weak spot is 2006 and 2007 (68%), when a new state law forced rollbacks and changed the rules. It is a modest predictor: it beats \"leave the rate alone\" only for school districts, because about half of counties and cities don't change their rate in a given year.";
  $("why-h-cov").textContent = "In every period after 2007 the share inside the band sits within a few points of the 80% target";
  (function () {
    const rows = Object.entries(EV.by_period), W = 620, H = 230, L = 52, R_ = 10, T = 18, Bm = 28, bw = (W - L - R_) / rows.length, s = svg(W, H), yy = v => T + (H - T - Bm) * (1 - v);
    s.setAttribute("aria-label", "Share of rate changes inside the 80% band by period");
    for (let v = 0; v <= 1.0001; v += 0.25) { el(s, "line", { x1: L, x2: W - R_, y1: yy(v), y2: yy(v), stroke: "var(--rule)" }); el(s, "text", { x: L - 6, y: yy(v) + 4, "text-anchor": "end" }, pc(v)); }
    rows.forEach(([k, v], i) => { const x = L + i * bw + bw * 0.2, w = bw * 0.6;
      el(s, "rect", { x, y: yy(v), width: w, height: yy(0) - yy(v), fill: "var(--accent)", rx: 2 });
      el(s, "text", { x: x + w / 2, y: yy(v) - 5, "text-anchor": "middle", class: "val" }, pc(v));
      el(s, "text", { x: x + w / 2, y: H - 8, "text-anchor": "middle" }, k); });
    el(s, "line", { x1: L, x2: W - R_, y1: yy(0.8), y2: yy(0.8), stroke: "var(--rule-strong)", "stroke-width": 1.6, "stroke-dasharray": "5 4" });
    $("why-c-cov").innerHTML = ""; $("why-c-cov").appendChild(s);
  })();

  // 4) Walczak
  const r28 = RENT.years["2028"], unit = r28.a3_full_neutral / RENT.units, apt = r28.a3_full_neutral_apartments / RENT.apartment_units;
  $("why-h4").textContent = `A parcel-level study by Jared Walczak puts the 2028 shift at $${EV.walczak.per_unit_2028} a rental or second-home unit; the model says ${usd(unit)}`;
  $("why-p4").textContent = "Walczak Policy's September 2026 study of Amendment 3 works from the 2025 final rolls, parcel by parcel, and was not built from this model. If local governments replace the revenue the amendment removes, we compare the extra tax per home or unit without a homestead exemption.";
  $("why-t-walczak").innerHTML = "<thead><tr><th>2028, if localities replace the revenue</th><th>This model</th><th>Walczak</th></tr></thead><tbody>" +
    `<tr><td>Extra tax per home or unit without a homestead exemption</td><td>${usd(unit)}</td><td>$${EV.walczak.per_unit_2028}</td></tr>` +
    `<tr><td>Extra tax per apartment unit</td><td>${usd(apt)}</td><td>$${EV.walczak.per_apartment_2028}</td></tr></tbody>`;
})();
'''
