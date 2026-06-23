const TEAM_SIZE = 5;
const BAN_SIZE = 5;
const STORAGE_KEY = "mlbb_saved_comps";

const state = {
  heroes: [],
  heroesById: {},
  allies: Array(TEAM_SIZE).fill(null),
  enemies: Array(TEAM_SIZE).fill(null),
  allyBans: Array(BAN_SIZE).fill(null),
  enemyBans: Array(BAN_SIZE).fill(null),
  roleFilter: "all",
  laneFilters: new Set(),
  pendingHero: null,
  anchorHeroId: null,
  dragPayload: null,
  activeTab: "draft",
  counterTargetId: null,
  counterMyRole: null,
  counterMyLane: null,
  metaRoleFilter: "all",
  tierModeFilter: "overall",
  tierRoleFilter: "all",
  tierLaneFilter: "all",
  tierData: null,
  tierSelectedHeroId: null,
  pickVsEnemyId: null,
  gamePhase: "mid",
  gameGold: "even",
  gameSituation: "",
};

const INGAME_PHASES = [
  { id: "early", label: "Ранняя (0–8 мин)" },
  { id: "mid", label: "Средняя (8–15 мин)" },
  { id: "late", label: "Поздняя (15+ мин)" },
];

const INGAME_GOLD = [
  { id: "ahead", label: "Впереди" },
  { id: "even", label: "Равно" },
  { id: "behind", label: "Отстаём" },
];

const INGAME_SITUATIONS = [
  { id: "", label: "Обычная игра" },
  { id: "teamfight", label: "Командный бой" },
  { id: "split", label: "Сплит-пуш" },
  { id: "defend", label: "Защита базы" },
];
const TIER_MODES = [
  { id: "overall", label: "Общий" },
  { id: "draft", label: "Драфт" },
  { id: "winrate", label: "Винрейт" },
  { id: "pick", label: "Пикрейт" },
  { id: "ban", label: "Банрейт" },
  { id: "early", label: "Ранняя" },
  { id: "mid", label: "Средняя" },
  { id: "late", label: "Поздняя" },
];

const TIER_TAG_LABELS = {
  "must-ban": "Must ban",
  "частый бан": "Частый бан",
  "перепик": "Перепик",
  "недооценён": "Недооценён",
  "синергист": "Синергист",
  "контрпикер": "Контрпикер",
  "уязвим": "Уязвим",
  "стабилен": "Стабилен",
};

const TIER_ORDER = ["S", "A", "B", "C", "D"];

const TIER_LABELS = {
  S: "S — топ мета",
  A: "A — сильные",
  B: "B — рабочие",
  C: "C — ситуативные",
  D: "D — слабые",
};

const ROLES = ["all", "Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support"];
const PLAYABLE_ROLES = ["Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support"];
const ROLE_LABELS = {
  all: "Все",
  Tank: "Танк",
  Fighter: "Боец",
  Assassin: "Ассасин",
  Mage: "Маг",
  Marksman: "Стрелок",
  Support: "Саппорт",
};

const LANES = [
  { id: "Gold Lane", label: "Голд" },
  { id: "Mid Lane", label: "Мид" },
  { id: "Exp Lane", label: "Эксп" },
  { id: "Roam", label: "Роам" },
  { id: "Jungle", label: "Лес" },
];

const LANE_LABELS = Object.fromEntries(LANES.map((l) => [l.id, l.label]));

const $ = (sel) => document.querySelector(sel);

function heroImage(hero) {
  return hero?.image || "";
}

function heroPortrait(src, alt = "", size = "md", className = "") {
  const image = typeof src === "object" && src !== null ? heroImage(src) : (src || "");
  const name = typeof src === "object" && src !== null ? (src.name || alt) : alt;
  const extra = className ? ` ${className}` : "";
  if (!image) {
    return `<div class="hero-portrait hero-portrait--${size} hero-portrait--empty${extra}"></div>`;
  }
  return `<div class="hero-portrait hero-portrait--${size}${extra}"><img src="${image}" alt="${name}" loading="lazy" draggable="false"></div>`;
}

function banArray(team) {
  return team === "enemy" ? state.enemyBans : state.allyBans;
}

function banList(team) {
  return banArray(team).filter((id) => id !== null);
}

function allDraftIds() {
  return [
    ...teamList("ally"),
    ...teamList("enemy"),
    ...banList("ally"),
    ...banList("enemy"),
  ];
}

function isHeroInDraft(heroId) {
  return allDraftIds().includes(heroId);
}

function draftPayload() {
  return {
    allies: teamList("ally"),
    enemies: teamList("enemy"),
    ally_bans: banList("ally"),
    enemy_bans: banList("enemy"),
  };
}

function idsParam(ids) {
  return ids.join(",");
}

function teamArray(team) {
  return team === "enemy" ? state.enemies : state.allies;
}

function teamList(team) {
  return teamArray(team).filter((id) => id !== null);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Ошибка API");
  }
  return data;
}

function roleBadge(role) {
  const label = ROLE_LABELS[role] || role || "Боец";
  const cls = (role || "fighter").toLowerCase().replace(/\s+/g, "");
  return `<span class="role-tag role-tag--${cls}">${label}</span>`;
}

function laneLabel(lane) {
  if (!lane) return "";
  return `<span class="lane-tag">${LANE_LABELS[lane] || lane}</span>`;
}

function setStatus(text, type = "") {
  const badge = $("#statusBadge");
  badge.textContent = text;
  badge.className = "header__status" + (type ? ` ${type}` : "");
}

function formatRefreshProgress(status) {
  const parts = [];
  if (status.step_label) parts.push(status.step_label);
  if (status.current != null && status.total) parts.push(`${status.current}/${status.total}`);
  if (status.heroes_total) {
    const loaded = status.heroes_loaded ?? status.current ?? 0;
    parts.push(`героев: ${loaded}/${status.heroes_total}`);
  }
  if (status.compat_loaded) parts.push(`синергии: ${status.compat_loaded}`);
  if (status.counters_loaded) parts.push(`контрпики: ${status.counters_loaded}`);
  if (status.hero_name) parts.push(status.hero_name);
  return parts.join(" · ");
}

function renderRefreshProgress(status) {
  const wrap = $("#refreshProgress");
  const fill = $("#refreshProgressFill");
  const meta = $("#refreshProgressMeta");
  if (!wrap || !fill || !meta) return;

  if (status.status !== "running") {
    wrap.classList.add("hidden");
    return;
  }

  wrap.classList.remove("hidden");
  const pct = status.percent ?? (status.total ? Math.round((status.current / status.total) * 100) : 0);
  fill.style.width = `${Math.min(100, Math.max(0, pct))}%`;
  meta.textContent = formatRefreshProgress(status);
  setStatus(status.message || formatRefreshProgress(status), "running");
}

function formatUpdatedAt(iso) {
  if (!iso) return "Данные: дата неизвестна";
  try {
    const d = new Date(iso);
    return `Данные от ${d.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  } catch {
    return `Данные от ${iso}`;
  }
}

function setDataUpdated(iso) {
  const el = $("#dataUpdated");
  if (el) el.textContent = formatUpdatedAt(iso);
}

let refreshPollTimer = null;

function stopRefreshPoll() {
  if (refreshPollTimer) {
    clearInterval(refreshPollTimer);
    refreshPollTimer = null;
  }
}

async function pollRefreshStatus() {
  try {
    const status = await api("/api/refresh-status");
    if (status.status === "running") {
      renderRefreshProgress(status);
      return;
    }
    stopRefreshPoll();
    $("#refreshProgress")?.classList.add("hidden");
    const health = await api("/api/health");
    setDataUpdated(health.updated_at);
    if (status.status === "error") {
      setStatus(status.message || "Ошибка обновления", "error");
    } else if (status.status === "done") {
      const heroes = status.heroes_loaded || health.heroes;
      setStatus(`${heroes} героев · данные обновлены`, "ok");
      if (state.activeTab === "meta") fetchMetaTops();
      if (state.activeTab === "tiers") fetchTierList();
      state.heroes = (await api("/api/heroes")).heroes;
      state.heroesById = Object.fromEntries(state.heroes.map((h) => [h.id, h]));
      renderAll();
      renderCounterHeroGrid();
    }
  } catch (err) {
    stopRefreshPoll();
    setStatus(err.message, "error");
  }
}

async function startDataRefresh(full = false) {
  const btns = [$("#refreshDataBtn"), $("#refreshDataFullBtn")].filter(Boolean);
  btns.forEach((btn) => { btn.disabled = true; });
  try {
    await api(`/api/refresh-data?full=${full ? "true" : "false"}`, { method: "POST" });
    setStatus(
      full ? "Полное обновление запущено (~40–60 мин)..." : "Обновление запущено (~10–20 мин)...",
      "running",
    );
    stopRefreshPoll();
    refreshPollTimer = setInterval(pollRefreshStatus, 1500);
    pollRefreshStatus();
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    btns.forEach((btn) => { btn.disabled = false; });
  }
}

function clearHeroFromTeams(heroId) {
  state.enemies = state.enemies.map((id) => (id === heroId ? null : id));
  state.allies = state.allies.map((id) => (id === heroId ? null : id));
  state.allyBans = state.allyBans.map((id) => (id === heroId ? null : id));
  state.enemyBans = state.enemyBans.map((id) => (id === heroId ? null : id));
  if (state.anchorHeroId === heroId) {
    const allies = teamList("ally");
    state.anchorHeroId = allies.length ? allies[allies.length - 1] : null;
  }
  if (state.pickVsEnemyId === heroId) state.pickVsEnemyId = null;
}

function placeHeroAt(team, index, heroId) {
  if (!heroId || index < 0 || index >= TEAM_SIZE) return;

  const arr = teamArray(team);
  const other = team === "enemy" ? state.allies : state.enemies;

  for (let i = 0; i < TEAM_SIZE; i++) {
    if (other[i] === heroId) other[i] = null;
  }
  state.allyBans = state.allyBans.map((id) => (id === heroId ? null : id));
  state.enemyBans = state.enemyBans.map((id) => (id === heroId ? null : id));

  const fromIdx = arr.indexOf(heroId);
  const displaced = arr[index];

  if (fromIdx >= 0 && fromIdx !== index) {
    arr[fromIdx] = null;
  }

  arr[index] = heroId;

  if (displaced && displaced !== heroId) {
    if (fromIdx >= 0 && fromIdx !== index) {
      arr[fromIdx] = displaced;
    } else {
      const emptyIdx = arr.indexOf(null);
      if (emptyIdx >= 0) arr[emptyIdx] = displaced;
    }
  }

  if (team === "ally") state.anchorHeroId = heroId;
  renderAll();
  scheduleAnalyze();
}

function firstEmptySlot(team) {
  return teamArray(team).indexOf(null);
}

function addHero(team, heroId) {
  const idx = firstEmptySlot(team);
  if (idx < 0) return;
  placeHeroAt(team, idx, heroId);
}

function removeHero(team, index) {
  const arr = teamArray(team);
  const removed = arr[index];
  if (!removed) return;
  arr[index] = null;
  if (state.anchorHeroId === removed) {
    const allies = teamList("ally");
    state.anchorHeroId = allies.length ? allies[allies.length - 1] : null;
  }
  renderAll();
  scheduleAnalyze();
}

function addBan(team, heroId) {
  const arr = banArray(team);
  const idx = arr.indexOf(null);
  if (idx < 0) return;
  clearHeroFromTeams(heroId);
  arr[idx] = heroId;
  renderAll();
  scheduleAnalyze();
}

function removeBan(team, index) {
  banArray(team)[index] = null;
  renderAll();
  scheduleAnalyze();
}

function clearDraft() {
  state.allies = Array(TEAM_SIZE).fill(null);
  state.enemies = Array(TEAM_SIZE).fill(null);
  state.allyBans = Array(BAN_SIZE).fill(null);
  state.enemyBans = Array(BAN_SIZE).fill(null);
  state.anchorHeroId = null;
  state.pickVsEnemyId = null;
  renderAll();
  showEmptyResults();
  fetchIngameAdvice();
}

function setDragPayload(payload) {
  state.dragPayload = payload;
}

function handleDrop(team, index, isBan = false) {
  const payload = state.dragPayload;
  if (!payload?.heroId) return;
  if (isBan) {
    const arr = banArray(team);
    if (arr[index] === null) {
      clearHeroFromTeams(payload.heroId);
      arr[index] = payload.heroId;
      renderAll();
      scheduleAnalyze();
    }
  } else {
    placeHeroAt(team, index, payload.heroId);
  }
  state.dragPayload = null;
}

function setupSlotDnD(slot, team, index, isBan = false) {
  slot.addEventListener("dragover", (e) => {
    e.preventDefault();
    slot.classList.add("slot--dragover");
  });
  slot.addEventListener("dragleave", () => {
    slot.classList.remove("slot--dragover");
  });
  slot.addEventListener("drop", (e) => {
    e.preventDefault();
    slot.classList.remove("slot--dragover");
    handleDrop(team, index, isBan);
  });
}

function setupHeroDrag(el, payload) {
  el.draggable = true;
  el.addEventListener("dragstart", (e) => {
    setDragPayload(payload);
    el.classList.add("is-dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(payload.heroId));
  });
  el.addEventListener("dragend", () => {
    el.classList.remove("is-dragging");
    document.querySelectorAll(".slot--dragover").forEach((n) => n.classList.remove("slot--dragover"));
    state.dragPayload = null;
  });
}

function renderSlots() {
  const enemySlots = $("#enemySlots");
  const allySlots = $("#allySlots");
  $("#enemyCount").textContent = teamList("enemy").length;
  $("#allyCount").textContent = teamList("ally").length;
  $("#enemyBanCount").textContent = banList("enemy").length;
  $("#allyBanCount").textContent = banList("ally").length;

  enemySlots.innerHTML = "";
  allySlots.innerHTML = "";

  for (let i = 0; i < TEAM_SIZE; i++) {
    enemySlots.appendChild(createSlot(state.enemies[i], "enemy", i));
    allySlots.appendChild(createSlot(state.allies[i], "ally", i));
  }

  renderBanSlots();
}

function renderBanSlots() {
  const enemyBanSlots = $("#enemyBanSlots");
  const allyBanSlots = $("#allyBanSlots");
  if (!enemyBanSlots || !allyBanSlots) return;
  enemyBanSlots.innerHTML = "";
  allyBanSlots.innerHTML = "";
  for (let i = 0; i < BAN_SIZE; i++) {
    enemyBanSlots.appendChild(createBanSlot(state.enemyBans[i], "enemy", i));
    allyBanSlots.appendChild(createBanSlot(state.allyBans[i], "ally", i));
  }
}

function createBanSlot(heroId, team, index) {
  const slot = document.createElement("div");
  slot.className = "slot slot--ban" + (heroId ? " filled" : "");
  slot.dataset.team = team;
  slot.dataset.banIndex = String(index);

  setupSlotDnD(slot, team, index, true);

  if (heroId) {
    const hero = state.heroesById[heroId];
    slot.innerHTML = `
      ${heroPortrait(hero, hero.name, "slot")}
      <button type="button" class="slot__remove" aria-label="Убрать">×</button>
    `;
    slot.querySelector(".slot__remove").addEventListener("click", (e) => {
      e.stopPropagation();
      removeBan(team, index);
    });
    setupHeroDrag(slot, { source: "ban", team, index, heroId });
  } else {
    slot.innerHTML = `<span class="slot__placeholder">✕</span>`;
  }
  return slot;
}

function createSlot(heroId, team, index) {
  const slot = document.createElement("div");
  const isAnchor = team === "ally" && heroId && state.anchorHeroId === heroId;
  slot.className = "slot" + (heroId ? " filled" : "") + (isAnchor ? " slot--anchor" : "");
  slot.dataset.team = team;
  slot.dataset.index = String(index);

  setupSlotDnD(slot, team, index);

  if (heroId) {
    const hero = state.heroesById[heroId];
    slot.innerHTML = `
      ${heroPortrait(hero, hero.name, "slot")}
      <span class="slot__role">${roleBadge(hero.role)}</span>
      <button type="button" class="slot__remove" aria-label="Убрать">×</button>
    `;
    slot.querySelector(".slot__remove").addEventListener("click", (e) => {
      e.stopPropagation();
      removeHero(team, index);
    });
    if (team === "ally") {
      slot.addEventListener("click", () => {
        state.anchorHeroId = heroId;
        renderAll();
        scheduleAnalyze();
      });
    }
    setupHeroDrag(slot, { source: "slot", team, index, heroId });
  } else {
    slot.innerHTML = `<span class="slot__placeholder">+</span>`;
  }
  return slot;
}

function renderRoleFilters() {
  refreshAllFilters();
}

function renderLaneFilters() {
  refreshAllFilters();
}

function heroSearchHaystack(hero) {
  return [hero.name, hero.name_ru].filter(Boolean).map((n) => n.toLowerCase());
}

function heroMatchesSearch(hero, searchValue) {
  if (!searchValue) return true;
  return heroSearchHaystack(hero).some((name) => name.includes(searchValue));
}

function heroPassesFilters(hero, searchValue = "") {
  const roleOk = state.roleFilter === "all" || hero.role === state.roleFilter;
  const searchOk = heroMatchesSearch(hero, searchValue);
  let laneOk = true;
  if (state.laneFilters.size > 0) {
    laneOk = hero.lane && state.laneFilters.has(hero.lane);
  }
  return roleOk && searchOk && laneOk;
}

function renderHeroGrid() {
  const grid = $("#heroGrid");
  grid.innerHTML = "";

  const filtered = state.heroes.filter((h) =>
    heroPassesFilters(h, $("#heroSearch").value.trim().toLowerCase())
  );

  filtered.forEach((hero) => {
    const card = document.createElement("div");
    card.className = "hero-card";
    card.setAttribute("role", "button");
    card.tabIndex = 0;
    if (teamList("enemy").includes(hero.id)) card.classList.add("selected-enemy");
    if (teamList("ally").includes(hero.id)) card.classList.add("selected-ally");
    if (banList("ally").includes(hero.id)) card.classList.add("selected-ban-ally");
    if (banList("enemy").includes(hero.id)) card.classList.add("selected-ban-enemy");

    card.innerHTML = `
      ${heroPortrait(hero, hero.name, "lg")}
      <div class="hero-card__meta">${roleBadge(hero.role)}${laneLabel(hero.lane)}</div>
      <div class="hero-card__name">${hero.name}</div>
    `;

    setupHeroDrag(card, { source: "grid", heroId: hero.id });

    card.addEventListener("click", () => openPicker(hero));
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openPicker(hero);
      }
    });

    grid.appendChild(card);
  });
}

function openPicker(hero) {
  if (isHeroInDraft(hero.id)) {
    clearHeroFromTeams(hero.id);
    renderAll();
    scheduleAnalyze();
    return;
  }

  state.pendingHero = hero;
  $("#pickerHero").innerHTML = `
    ${heroPortrait(hero, hero.name, "xl")}
    <div>
      <div style="font-weight:800;font-size:1.1rem">${hero.name}</div>
      <div style="margin-top:6px">${roleBadge(hero.role)} ${laneLabel(hero.lane)}</div>
    </div>
  `;
  $("#pickerOverlay").classList.remove("hidden");
}

function closePicker() {
  state.pendingHero = null;
  $("#pickerOverlay").classList.add("hidden");
}

function renderPartnerCard(combo, rank, anchorId) {
  const partnerId = combo.heroes.find((id) => id !== anchorId) ?? combo.heroes[1];
  const partnerIdx = combo.heroes.indexOf(partnerId);
  const partner = state.heroesById[partnerId];
  const anchor = state.heroesById[anchorId];
  const notes = combo.notes?.length
    ? `<ul class="combo-card__notes">${combo.notes.map((n) => `<li>${n}</li>`).join("")}</ul>`
    : "";

  return `
    <article class="combo-card combo-card--partner">
      <div class="combo-card__top">
        <div class="combo-card__heroes">
          <div class="combo-hero combo-hero--anchor">
            ${heroPortrait(anchor, anchor?.name, "sm")}
            <div>
              <span>${anchor?.name}</span>
              ${roleBadge(anchor?.role)}
            </div>
          </div>
          <span class="combo-plus">+</span>
          <div class="combo-hero combo-hero--pick">
            ${heroPortrait(partner, combo.hero_names[partnerIdx], "sm")}
            <div>
              <span>${combo.hero_names[partnerIdx]}</span>
              ${roleBadge(partner?.role)} ${laneLabel(partner?.lane)}
            </div>
          </div>
        </div>
        <div class="combo-card__score">#${rank} · ${combo.score}</div>
      </div>
      <div class="combo-card__metrics">
        <span class="metric">Синергия <strong>${(combo.synergy * 100).toFixed(1)}%</strong></span>
        <span class="metric">Контр <strong>${(combo.counter * 100).toFixed(1)}%</strong></span>
        <span class="metric">Угроза <strong>${(combo.threat * 100).toFixed(1)}%</strong></span>
      </div>
      ${notes}
    </article>
  `;
}

function renderComboCard(combo, rank) {
  const heroesHtml = combo.heroes
    .map((id, idx) => {
      const hero = state.heroesById[id];
      return `
        <div class="combo-hero">
          ${heroPortrait(hero, combo.hero_names[idx], "sm")}
          <div>
            <span>${combo.hero_names[idx]}</span>
            ${roleBadge(hero?.role)} ${laneLabel(hero?.lane)}
          </div>
        </div>
      `;
    })
    .join("");

  const notes = combo.notes?.length
    ? `<ul class="combo-card__notes">${combo.notes.map((n) => `<li>${n}</li>`).join("")}</ul>`
    : "";

  return `
    <article class="combo-card">
      <div class="combo-card__top">
        <div class="combo-card__heroes">${heroesHtml}</div>
        <div class="combo-card__score">#${rank} · ${combo.score}</div>
      </div>
      <div class="combo-card__metrics">
        <span class="metric">Синергия <strong>${(combo.synergy * 100).toFixed(1)}%</strong></span>
        <span class="metric">Контр <strong>${(combo.counter * 100).toFixed(1)}%</strong></span>
        <span class="metric">Угроза <strong>${(combo.threat * 100).toFixed(1)}%</strong></span>
        <span class="metric">Роли <strong>${combo.roles.join(", ")}</strong></span>
      </div>
      ${notes}
    </article>
  `;
}

function renderPhaseBars(label, phases) {
  if (!phases) return "";
  const items = [
    { key: "early", label: "Ранняя" },
    { key: "mid", label: "Средняя" },
    { key: "late", label: "Поздняя" },
  ];
  return `
    <div class="prediction__phase-group">
      <div class="prediction__phase-title">${label}</div>
      ${items
        .map(
          (item) => `
        <div class="prediction__phase-row">
          <span>${item.label}</span>
          <div class="prediction__phase-track">
            <div class="prediction__phase-fill" style="width:${phases[item.key] || 0}%"></div>
          </div>
          <strong>${phases[item.key] || 0}%</strong>
        </div>`,
        )
        .join("")}
    </div>
  `;
}

function renderPrediction(prediction) {
  const block = $("#predictionBlock");
  if (!prediction) {
    block.classList.add("hidden");
    block.innerHTML = "";
    return;
  }

  const winnerClass =
    prediction.winner === "allies"
      ? "prediction--ally"
      : prediction.winner === "enemies"
        ? "prediction--enemy"
        : "prediction--even";

  const notes = prediction.notes?.length
    ? `<ul class="prediction__notes">${prediction.notes.map((n) => `<li>${n}</li>`).join("")}</ul>`
    : "";

  const phasesBlock =
    prediction.ally_phases && prediction.enemy_phases
      ? `<div class="prediction__phases">
          ${renderPhaseBars("Союзники", prediction.ally_phases)}
          ${renderPhaseBars("Враги", prediction.enemy_phases)}
        </div>`
      : "";

  block.className = `prediction ${winnerClass}`;
  block.innerHTML = `
    <div class="prediction__main">
      <div>
        <div class="prediction__label">Прогноз матча</div>
        <div class="prediction__winner">${prediction.winner_label}</div>
      </div>
      <div class="prediction__chance">
        <span>${prediction.ally_win_chance}%</span>
        <small>шанс союзников</small>
      </div>
    </div>
    <div class="prediction__bar">
      <div class="prediction__bar-ally" style="width:${prediction.ally_win_chance}%"></div>
    </div>
    ${phasesBlock}
    <div class="prediction__stats">
      <span>Союзники: ${prediction.ally_score}</span>
      <span>Враги: ${prediction.enemy_score}</span>
      <span>Синергия ${(prediction.ally_synergy * 100).toFixed(1)}% / ${(prediction.enemy_synergy * 100).toFixed(1)}%</span>
      <span>Контр ${(prediction.ally_counter * 100).toFixed(1)}% / ${(prediction.enemy_counter * 100).toFixed(1)}%</span>
    </div>
    ${notes}
  `;
  block.classList.remove("hidden");
}

function renderAnchorPicker() {
  const wrap = $("#anchorPicker");
  const allies = teamList("ally");
  if (!allies.length) {
    wrap.classList.add("hidden");
    wrap.innerHTML = "";
    return;
  }
  wrap.classList.remove("hidden");
  wrap.innerHTML = `<span class="anchor-picker__label">Кого пары подбираем:</span>`;
  allies.forEach((id) => {
    const hero = state.heroesById[id];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "anchor-chip" + (state.anchorHeroId === id ? " active" : "");
    btn.innerHTML = `${hero.name} ${roleBadge(hero.role)}`;
    btn.addEventListener("click", () => {
      state.anchorHeroId = id;
      renderAll();
      scheduleAnalyze();
    });
    wrap.appendChild(btn);
  });
}

function renderAdviceCard(pick, rank) {
  const reasons = pick.reasons?.map((r) => `<li>${r}</li>`).join("") || "";
  return `
    <article class="advice-card ${pick.priority === "high" ? "advice-card--high" : ""}">
      <div class="advice-card__hero">
        ${heroPortrait(pick.image, pick.hero_name, "md")}
        <div>
          <strong>#${rank} ${pick.hero_name}</strong>
          <div style="margin-top:4px">${roleBadge(pick.role)} ${laneLabel(pick.lane)}</div>
        </div>
      </div>
      <ul class="advice-card__reasons">${reasons}</ul>
      <div class="advice-card__actions">
        <span class="advice-card__score">${pick.score}</span>
        <button type="button" class="btn btn--primary btn--small advice-add" data-hero-id="${pick.hero_id}">
          Взять
        </button>
      </div>
    </article>
  `;
}

function renderAdvice(advice, options = {}) {
  const {
    blockId = "adviceBlock",
    tipsId = "adviceTips",
    listId = "adviceList",
    showAdd = true,
  } = options;

  const block = document.getElementById(blockId);
  const tipsEl = document.getElementById(tipsId);
  const listEl = document.getElementById(listId);
  if (!block || !tipsEl || !listEl) return;

  const picks = advice?.picks || [];
  const tips = advice?.tips || [];

  if (!picks.length && !tips.length) {
    block.classList.add("hidden");
    return;
  }

  block.classList.remove("hidden");

  if (tips.length) {
    tipsEl.classList.remove("hidden");
    tipsEl.innerHTML = tips.map((t) => `<li>${t}</li>`).join("");
  } else {
    tipsEl.classList.add("hidden");
    tipsEl.innerHTML = "";
  }

  if (picks.length) {
    listEl.innerHTML = picks.map((p, i) => renderAdviceCard(p, i + 1)).join("");
    if (showAdd) {
      listEl.querySelectorAll(".advice-add").forEach((btn) => {
        btn.addEventListener("click", () => {
          const heroId = Number(btn.dataset.heroId);
          addHero("ally", heroId);
        });
      });
    }
  } else {
    listEl.innerHTML = "<p style='color:#94a3b8'>Состав полный или нет данных для советов</p>";
  }
}

function renderBanCard(ban, rank) {
  const reasons = ban.reasons?.map((r) => `<li>${r}</li>`).join("") || "";
  return `
    <article class="advice-card">
      <div class="advice-card__hero">
        ${heroPortrait(ban.image, ban.hero_name, "md")}
        <div>
          <strong>#${rank} ${ban.hero_name}</strong>
          <div style="margin-top:4px">${roleBadge(ban.role)} ${laneLabel(ban.lane)}</div>
        </div>
      </div>
      <ul class="advice-card__reasons">${reasons}</ul>
      <div class="advice-card__actions">
        <span class="advice-card__score">${ban.ban_percent}%</span>
        <button type="button" class="btn btn--ghost btn--small advice-ban" data-hero-id="${ban.hero_id}">Бан</button>
      </div>
    </article>
  `;
}

function renderBanAdvice(banAdvice) {
  const block = $("#banAdviceBlock");
  const tipsEl = $("#banAdviceTips");
  const listEl = $("#banAdviceList");
  if (!block || !listEl) return;

  const bans = banAdvice?.bans || [];
  const tips = banAdvice?.tips || [];
  if (!bans.length && !tips.length) {
    block.classList.add("hidden");
    return;
  }

  block.classList.remove("hidden");
  if (tips.length && tipsEl) {
    tipsEl.classList.remove("hidden");
    tipsEl.innerHTML = tips.map((t) => `<li>${t}</li>`).join("");
  } else if (tipsEl) {
    tipsEl.classList.add("hidden");
  }

  listEl.innerHTML = bans.map((b, i) => renderBanCard(b, i + 1)).join("");
  listEl.querySelectorAll(".advice-ban").forEach((btn) => {
    btn.addEventListener("click", () => {
      addBan("ally", Number(btn.dataset.heroId));
    });
  });
}

function renderPickVsSelect() {
  const select = $("#pickVsSelect");
  if (!select) return;
  const current = state.pickVsEnemyId || select.value || "";
  select.innerHTML = '<option value="">Выберите вражеского героя</option>';
  state.heroes.forEach((hero) => {
    const opt = document.createElement("option");
    opt.value = String(hero.id);
    opt.textContent = hero.name;
    if (String(hero.id) === String(current)) opt.selected = true;
    select.appendChild(opt);
  });
  teamList("enemy").forEach((id) => {
    if (!select.querySelector(`option[value="${id}"]`)) return;
    const opt = select.querySelector(`option[value="${id}"]`);
    opt.textContent = `${state.heroesById[id].name} (в драфте)`;
  });
}

async function fetchPickVs() {
  const enemyId = state.pickVsEnemyId || Number($("#pickVsSelect")?.value);
  const block = $("#pickVsBlock");
  if (!enemyId || !block) {
    block?.classList.add("hidden");
    return;
  }

  const payload = draftPayload();
  const params = new URLSearchParams({
    allies: idsParam(payload.allies),
    enemies: idsParam(payload.enemies),
    ally_bans: idsParam(payload.ally_bans),
    enemy_bans: idsParam(payload.enemy_bans),
    limit: "8",
  });

  try {
    const data = await api(`/api/pick-vs/${enemyId}?${params}`);
    block.classList.remove("hidden");

    const tipsEl = $("#pickVsTips");
    if (data.tips?.length && tipsEl) {
      tipsEl.classList.remove("hidden");
      tipsEl.innerHTML = data.tips.map((t) => `<li>${t}</li>`).join("");
    }

    const listEl = $("#pickVsList");
    if (listEl) {
      listEl.innerHTML = (data.picks || [])
        .map((p, i) => renderAdviceCard(p, i + 1))
        .join("") || "<p style='color:#94a3b8'>Нет подходящих пиков</p>";
      listEl.querySelectorAll(".advice-add").forEach((btn) => {
        btn.addEventListener("click", () => addHero("ally", Number(btn.dataset.heroId)));
      });
    }

    const countersEl = $("#pickVsCounters");
    if (countersEl && data.counters?.length) {
      countersEl.classList.remove("hidden");
      countersEl.innerHTML = data.counters
        .map((c, i) => renderCounterCard(c, i + 1))
        .join("");
    } else if (countersEl) {
      countersEl.classList.add("hidden");
    }
  } catch (err) {
    console.error(err);
  }
}

function loadSavedComps() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveSavedComps(comps) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(comps));
}

function renderSavedComps() {
  const select = $("#savedCompSelect");
  if (!select) return;
  const comps = loadSavedComps();
  const current = select.value;
  select.innerHTML = '<option value="">Загрузить состав...</option>';
  comps.forEach((comp) => {
    const opt = document.createElement("option");
    opt.value = comp.id;
    const date = new Date(comp.savedAt).toLocaleDateString("ru-RU");
    opt.textContent = `${comp.name} (${date})`;
    select.appendChild(opt);
  });
  if (current) select.value = current;
}

function saveComposition() {
  const name = ($("#compName")?.value || "").trim() || `Состав ${new Date().toLocaleString("ru-RU")}`;
  const comps = loadSavedComps();
  const comp = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    allies: [...state.allies],
    enemies: [...state.enemies],
    allyBans: [...state.allyBans],
    enemyBans: [...state.enemyBans],
    savedAt: new Date().toISOString(),
  };
  comps.unshift(comp);
  saveSavedComps(comps.slice(0, 20));
  renderSavedComps();
  if ($("#compName")) $("#compName").value = "";
}

function loadComposition(id) {
  const comp = loadSavedComps().find((c) => c.id === id);
  if (!comp) return;
  state.allies = [...comp.allies];
  state.enemies = [...comp.enemies];
  state.allyBans = [...(comp.allyBans || Array(BAN_SIZE).fill(null))];
  state.enemyBans = [...(comp.enemyBans || Array(BAN_SIZE).fill(null))];
  while (state.allies.length < TEAM_SIZE) state.allies.push(null);
  while (state.enemies.length < TEAM_SIZE) state.enemies.push(null);
  while (state.allyBans.length < BAN_SIZE) state.allyBans.push(null);
  while (state.enemyBans.length < BAN_SIZE) state.enemyBans.push(null);
  const allies = teamList("ally");
  state.anchorHeroId = allies.length ? allies[allies.length - 1] : null;
  renderAll();
  scheduleAnalyze();
  fetchIngameAdvice();
}

function deleteComposition() {
  const id = $("#savedCompSelect")?.value;
  if (!id) return;
  saveSavedComps(loadSavedComps().filter((c) => c.id !== id));
  renderSavedComps();
}

function renderIngameDraftPreview() {
  const wrap = $("#ingameDraftPreview");
  if (!wrap) return;
  const allies = teamList("ally");
  const enemies = teamList("enemy");
  if (!allies.length && !enemies.length) {
    wrap.innerHTML = '<p class="ingame-draft-preview__empty">Заполните драфт на вкладке «Драфт»</p>';
    return;
  }
  const renderTeam = (ids, label) => {
    if (!ids.length) return `<div><strong>${label}:</strong> —</div>`;
    return `<div><strong>${label}:</strong> ${ids.map((id) => state.heroesById[id]?.name || id).join(", ")}</div>`;
  };
  wrap.innerHTML = `${renderTeam(allies, "Союзники")}${renderTeam(enemies, "Враги")}`;
}

function renderIngameFilters() {
  const phaseWrap = $("#ingamePhaseFilters");
  const goldWrap = $("#ingameGoldFilters");
  const sitWrap = $("#ingameSituationFilters");
  if (!phaseWrap) return;

  phaseWrap.innerHTML = "";
  INGAME_PHASES.forEach((item) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (state.gamePhase === item.id ? " active" : "");
    btn.textContent = item.label;
    btn.addEventListener("click", () => {
      state.gamePhase = item.id;
      renderIngameFilters();
      fetchIngameAdvice();
    });
    phaseWrap.appendChild(btn);
  });

  goldWrap.innerHTML = "";
  INGAME_GOLD.forEach((item) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (state.gameGold === item.id ? " active" : "");
    btn.textContent = item.label;
    btn.addEventListener("click", () => {
      state.gameGold = item.id;
      renderIngameFilters();
      fetchIngameAdvice();
    });
    goldWrap.appendChild(btn);
  });

  sitWrap.innerHTML = "";
  INGAME_SITUATIONS.forEach((item) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (state.gameSituation === item.id ? " active" : "");
    btn.textContent = item.label;
    btn.addEventListener("click", () => {
      state.gameSituation = item.id;
      renderIngameFilters();
      fetchIngameAdvice();
    });
    sitWrap.appendChild(btn);
  });
}

async function fetchIngameAdvice() {
  const tipsEl = $("#ingameTips");
  const phasesEl = $("#ingamePhases");
  if (!tipsEl) return;

  const payload = draftPayload();
  if (!payload.allies.length) {
    tipsEl.innerHTML = "<li>Добавьте союзников в драфте — тогда советы будут точнее</li>";
    phasesEl?.classList.add("hidden");
    return;
  }

  try {
    const data = await api("/api/ingame/advice", {
      method: "POST",
      body: JSON.stringify({
        allies: payload.allies,
        enemies: payload.enemies,
        phase: state.gamePhase,
        gold: state.gameGold,
        situation: state.gameSituation,
      }),
    });

    tipsEl.innerHTML = (data.tips || []).map((t) => `<li>${t}</li>`).join("")
      || "<li>Нет советов для текущей ситуации</li>";

    if (phasesEl && data.ally_phases && Object.keys(data.ally_phases).length) {
      phasesEl.classList.remove("hidden");
      phasesEl.innerHTML = `
        <div class="prediction__phases">
          ${renderPhaseBars("Союзники", data.ally_phases)}
          ${renderPhaseBars("Враги", data.enemy_phases || {})}
        </div>`;
    } else if (phasesEl) {
      phasesEl.classList.add("hidden");
    }
  } catch (err) {
    tipsEl.innerHTML = `<li style="color:#fca5a5">${err.message}</li>`;
  }
}

function renderResults(data) {
  const mode = $("#modeSelect").value;
  const hasEnemies = teamList("enemy").length > 0;
  const hasAllies = teamList("ally").length > 0;
  const anchorId = data.anchor || state.anchorHeroId;

  if (!hasEnemies && !hasAllies) {
    showEmptyResults();
    return;
  }

  $("#resultsEmpty").classList.add("hidden");
  $("#resultsContent").classList.remove("hidden");
  renderPrediction(data.prediction);
  renderAdvice(data.advice);
  renderBanAdvice(data.ban_advice);
  renderPickVsSelect();
  if (!state.pickVsEnemyId && teamList("enemy").length) {
    state.pickVsEnemyId = teamList("enemy")[teamList("enemy").length - 1];
    renderPickVsSelect();
  }
  if (state.pickVsEnemyId || $("#pickVsSelect")?.value) fetchPickVs();
  renderAnchorPicker();

  const partnerBlock = $("#partnerBlock");
  if (anchorId && data.partners?.length && (mode === "partner" || mode === "all" || mode === "duo" || mode === "complete")) {
    partnerBlock.classList.remove("hidden");
    $("#partnerAnchorBadge").textContent = `к ${data.anchor_name || state.heroesById[anchorId]?.name}`;
    $("#partnerList").innerHTML = data.partners
      .map((c, i) => renderPartnerCard(c, i + 1, anchorId))
      .join("");
  } else if (anchorId && hasAllies && mode === "partner") {
    partnerBlock.classList.remove("hidden");
    $("#partnerAnchorBadge").textContent = `к ${state.heroesById[anchorId]?.name}`;
    $("#partnerList").innerHTML = "<p style='color:#94a3b8'>Нет напарников</p>";
  } else if (mode !== "partner") {
    partnerBlock.classList.toggle("hidden", !anchorId || !data.partners?.length);
    if (anchorId && data.partners?.length) {
      $("#partnerAnchorBadge").textContent = `к ${data.anchor_name}`;
      $("#partnerList").innerHTML = data.partners
        .map((c, i) => renderPartnerCard(c, i + 1, anchorId))
        .join("");
    }
  } else {
    partnerBlock.classList.add("hidden");
  }

  const completeBlock = $("#completeBlock");
  if (mode === "complete" && hasAllies) {
    completeBlock.classList.remove("hidden");
    $("#completeList").innerHTML = data.complete
      .map((c, i) => renderComboCard(c, i + 1))
      .join("") || "<p style='color:#94a3b8'>Нет вариантов</p>";
  } else {
    completeBlock.classList.add("hidden");
  }

  if (mode === "duo" || mode === "all") {
    $("#duoList").parentElement.classList.remove("hidden");
    $("#duoList").innerHTML = data.duos
      .map((c, i) => renderComboCard(c, i + 1))
      .join("") || "<p style='color:#94a3b8'>Нет даблов</p>";
  } else if (mode !== "all") {
    $("#duoList").parentElement.classList.add("hidden");
  }

  if (mode === "trio" || mode === "all" || mode === "complete") {
    $("#trioList").parentElement.classList.remove("hidden");
    $("#trioList").innerHTML = data.trios
      .map((c, i) => renderComboCard(c, i + 1))
      .join("") || "<p style='color:#94a3b8'>Нет триплов</p>";
  } else {
    $("#trioList").parentElement.classList.add("hidden");
  }

  const teamBlock = $("#teamBlock");
  if (mode === "team" || mode === "all" || mode === "complete") {
    teamBlock.classList.remove("hidden");
    $("#teamList").innerHTML = data.teams
      .map((c, i) => renderComboCard(c, i + 1))
      .join("") || "<p style='color:#94a3b8'>Нет пятёрок</p>";
  } else {
    teamBlock.classList.add("hidden");
  }
}

function showEmptyResults() {
  $("#resultsEmpty").classList.remove("hidden");
  $("#resultsContent").classList.add("hidden");
  renderPrediction(null);
  $("#adviceBlock")?.classList.add("hidden");
}

let analyzeTimer = null;
function scheduleAnalyze() {
  clearTimeout(analyzeTimer);
  analyzeTimer = setTimeout(runAnalyze, 350);
}

async function runAnalyze() {
  const allies = teamList("ally");
  const enemies = teamList("enemy");
  if (!enemies.length && !allies.length) {
    showEmptyResults();
    return;
  }

  try {
    const payload = draftPayload();
    const data = await api("/api/analyze", {
      method: "POST",
      body: JSON.stringify({
        ...payload,
        anchor: state.anchorHeroId,
        mode: $("#modeSelect").value,
        limit: 12,
      }),
    });
    renderResults(data);
    fetchIngameAdvice();
  } catch (err) {
    console.error(err);
  }
}

function renderMetaRow(item, rank, type) {
  const valueKey = type === "pick" ? "pick_percent" : type === "ban" ? "ban_percent" : "win_percent";
  return `
    <div class="meta-row">
      <span class="meta-row__rank">#${rank}</span>
      ${heroPortrait(item.image, item.hero_name, "md")}
      <div class="meta-row__info">
        <strong>${item.hero_name}</strong>
        <div class="meta-row__meta">${roleBadge(item.role)} ${laneLabel(item.lane)}</div>
      </div>
      <span class="meta-row__value meta-row__value--${type}">${item[valueKey]}%</span>
    </div>
  `;
}

function renderMetaLists(data) {
  $("#metaPicksList").innerHTML = data.top_picks
    .map((h, i) => renderMetaRow(h, i + 1, "pick"))
    .join("");
  $("#metaBansList").innerHTML = data.top_bans
    .map((h, i) => renderMetaRow(h, i + 1, "ban"))
    .join("");
  $("#metaWinList").innerHTML = data.top_winrate
    .map((h, i) => renderMetaRow(h, i + 1, "win"))
    .join("");
}

function renderMetaRoleFilters() {
  const wrap = $("#metaRoleFilters");
  if (!wrap) return;
  wrap.innerHTML = "";
  ROLES.forEach((role) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (state.metaRoleFilter === role ? " active" : "");
    btn.textContent = ROLE_LABELS[role];
    btn.addEventListener("click", () => {
      state.metaRoleFilter = role;
      renderMetaRoleFilters();
      fetchMetaTops();
    });
    wrap.appendChild(btn);
  });
}

async function fetchMetaTops() {
  const roleParam =
    state.metaRoleFilter !== "all" ? `&role=${encodeURIComponent(state.metaRoleFilter)}` : "";
  try {
    const data = await api(`/api/meta/tops?limit=15${roleParam}`);
    renderMetaLists(data);
  } catch (err) {
    $("#metaPicksList").innerHTML = `<p style="color:#fca5a5">${err.message}</p>`;
    $("#metaBansList").innerHTML = "";
    $("#metaWinList").innerHTML = "";
  }
}

function renderTierMetricBar(label, value, tone = "") {
  return `
    <div class="tier-metric">
      <div class="tier-metric__head">
        <span>${label}</span>
        <strong>${value}%</strong>
      </div>
      <div class="tier-metric__track">
        <div class="tier-metric__fill tier-metric__fill--${tone}" style="width:${value}%"></div>
      </div>
    </div>
  `;
}

function renderTierHeroCard(hero) {
  const tags = (hero.tags || [])
    .map((tag) => `<span class="tier-tag tier-tag--${tag.replace(/\s+/g, "-")}">${TIER_TAG_LABELS[tag] || tag}</span>`)
    .join("");
  const selected = state.tierSelectedHeroId === hero.hero_id ? " tier-hero--selected" : "";
  return `
    <button type="button" class="tier-hero${selected}" data-hero-id="${hero.hero_id}">
      <div class="tier-hero__portrait">
        <span class="tier-hero__rank">#${hero.rank}</span>
        ${heroPortrait(hero.image, hero.hero_name, "xl")}
      </div>
      <strong class="tier-hero__name">${hero.hero_name}</strong>
      <div class="tier-hero__metrics">
        ${renderTierMetricBar("WR", hero.win_percent, "win")}
        ${renderTierMetricBar("Pick", hero.pick_percent, "pick")}
        ${renderTierMetricBar("Ban", Math.min(hero.ban_percent, 100), "ban")}
      </div>
      ${tags ? `<div class="tier-hero__tags">${tags}</div>` : ""}
    </button>
  `;
}

function findTierHero(heroId) {
  if (!state.tierData?.tiers) return null;
  for (const tier of TIER_ORDER) {
    const hero = (state.tierData.tiers[tier] || []).find((h) => h.hero_id === heroId);
    if (hero) return hero;
  }
  return null;
}

function renderTierDetail() {
  const panel = $("#tierDetail");
  if (!panel) return;
  const hero = state.tierSelectedHeroId ? findTierHero(state.tierSelectedHeroId) : null;
  if (!hero) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }

  const scores = hero.scores || {};
  panel.className = "tier-detail";
  panel.innerHTML = `
    <div class="tier-detail__head">
      ${heroPortrait(hero.image, hero.hero_name, "2xl")}
      <div>
        <h3>${hero.hero_name}</h3>
        <div class="tier-detail__meta">
          ${roleBadge(hero.role)} ${laneLabel(hero.lane)}
          <span class="tier-detail__tier">Тир ${hero.tier} · #${hero.rank}</span>
        </div>
      </div>
      <button type="button" class="tier-detail__close" id="tierDetailClose">×</button>
    </div>
    <p class="tier-detail__insight">${hero.insight || ""}</p>
    <div class="tier-detail__grid">
      <div>
        <h4>Мета</h4>
        ${renderTierMetricBar("Винрейт", hero.win_percent, "win")}
        ${renderTierMetricBar("Пикрейт", hero.pick_percent, "pick")}
        ${renderTierMetricBar("Банрейт", Math.min(hero.ban_percent, 100), "ban")}
      </div>
      <div>
        <h4>Драфт</h4>
        ${renderTierMetricBar("Синергии", scores.synergy || 0, "synergy")}
        ${renderTierMetricBar("Контрпики", scores.counter || 0, "counter")}
        ${renderTierMetricBar("Уязвимость", scores.vulnerability || 0, "risk")}
        ${renderTierMetricBar("Драфт-оценка", scores.draft || 0, "draft")}
      </div>
      <div>
        <h4>Фазы игры</h4>
        ${renderTierMetricBar("Ранняя", hero.phases?.early || 0, "early")}
        ${renderTierMetricBar("Средняя", hero.phases?.mid || 0, "mid")}
        ${renderTierMetricBar("Поздняя", hero.phases?.late || 0, "late")}
      </div>
    </div>
  `;
  $("#tierDetailClose")?.addEventListener("click", () => {
    state.tierSelectedHeroId = null;
    renderTierDetail();
    renderTierBoard(state.tierData);
  });
}

function renderTierSummary(data) {
  const wrap = $("#tierSummary");
  if (!wrap) return;
  if (!data?.has_meta) {
    wrap.classList.add("hidden");
    return;
  }
  const counts = data.tier_counts || {};
  wrap.className = "tier-summary";
  wrap.innerHTML = `
    <div class="tier-summary__item">
      <span>Героев в выборке</span>
      <strong>${data.total || 0}</strong>
    </div>
    <div class="tier-summary__item">
      <span>Режим</span>
      <strong>${data.mode_label || ""}</strong>
    </div>
    ${TIER_ORDER.map(
      (tier) => `
      <div class="tier-summary__item tier-summary__item--${tier.toLowerCase()}">
        <span>Тир ${tier}</span>
        <strong>${counts[tier] || 0}</strong>
      </div>`,
    ).join("")}
  `;
}

function renderTierHighlights(data) {
  const wrap = $("#tierHighlights");
  if (!wrap || !data?.highlights) return;
  const blocks = [
    { key: "must_ban", title: "Часто банят", tone: "ban" },
    { key: "hidden_gems", title: "Недооценённые", tone: "win" },
    { key: "overpicked", title: "Перепикнутые", tone: "risk" },
  ];
  const html = blocks
    .filter((block) => (data.highlights[block.key] || []).length)
    .map((block) => {
      const items = data.highlights[block.key]
        .map(
          (hero) => `
          <button type="button" class="tier-highlight-chip" data-hero-id="${hero.hero_id}">
            ${heroPortrait(hero.image, hero.hero_name, "xs")}
            <span>${hero.hero_name}</span>
            <small>${hero.win_percent}% WR</small>
          </button>`,
        )
        .join("");
      return `
        <div class="tier-highlight tier-highlight--${block.tone}">
          <div class="tier-highlight__title">${block.title}</div>
          <div class="tier-highlight__list">${items}</div>
        </div>`;
    })
    .join("");
  if (!html) {
    wrap.classList.add("hidden");
    wrap.innerHTML = "";
    return;
  }
  wrap.className = "tier-highlights";
  wrap.innerHTML = html;
  wrap.querySelectorAll("[data-hero-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.tierSelectedHeroId = Number(btn.dataset.heroId);
      renderTierDetail();
      renderTierBoard(state.tierData);
    });
  });
}

function renderTierBoard(data) {
  const board = $("#tierBoard");
  if (!board) return;
  board.innerHTML = TIER_ORDER.map((tier) => {
    const heroes = data.tiers?.[tier] || [];
    return `
      <div class="tier-row tier-row--${tier.toLowerCase()}">
        <div class="tier-row__label">${TIER_LABELS[tier]}</div>
        <div class="tier-row__heroes">
          ${
            heroes.length
              ? heroes.map(renderTierHeroCard).join("")
              : '<span class="tier-row__empty">—</span>'
          }
        </div>
      </div>
    `;
  }).join("");
  board.querySelectorAll(".tier-hero[data-hero-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const heroId = Number(btn.dataset.heroId);
      state.tierSelectedHeroId = state.tierSelectedHeroId === heroId ? null : heroId;
      renderTierDetail();
      renderTierBoard(data);
    });
  });
}

function renderTierModeFilters() {
  const wrap = $("#tierModeFilters");
  if (!wrap) return;
  wrap.innerHTML = "";
  TIER_MODES.forEach((mode) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (state.tierModeFilter === mode.id ? " active" : "");
    btn.textContent = mode.label;
    btn.addEventListener("click", () => {
      state.tierModeFilter = mode.id;
      renderTierModeFilters();
      fetchTierList();
    });
    wrap.appendChild(btn);
  });
}

function renderTierRoleFilters() {
  const wrap = $("#tierRoleFilters");
  if (!wrap) return;
  wrap.innerHTML = "";
  ROLES.forEach((role) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (state.tierRoleFilter === role ? " active" : "");
    btn.textContent = ROLE_LABELS[role];
    btn.addEventListener("click", () => {
      state.tierRoleFilter = role;
      renderTierRoleFilters();
      fetchTierList();
    });
    wrap.appendChild(btn);
  });
}

function renderTierLaneFilters() {
  const wrap = $("#tierLaneFilters");
  if (!wrap) return;
  wrap.innerHTML = "";
  const lanes = [{ id: "all", label: "Все" }, ...LANES];
  lanes.forEach((lane) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (state.tierLaneFilter === lane.id ? " active" : "");
    btn.textContent = lane.label;
    btn.addEventListener("click", () => {
      state.tierLaneFilter = lane.id;
      renderTierLaneFilters();
      fetchTierList();
    });
    wrap.appendChild(btn);
  });
}

async function fetchTierList() {
  const params = new URLSearchParams({ mode: state.tierModeFilter });
  if (state.tierRoleFilter !== "all") params.set("role", state.tierRoleFilter);
  if (state.tierLaneFilter !== "all") params.set("lane", state.tierLaneFilter);
  try {
    const data = await api(`/api/meta/tierlist?${params}`);
    state.tierData = data;
    if (
      state.tierSelectedHeroId &&
      !findTierHero(state.tierSelectedHeroId)
    ) {
      state.tierSelectedHeroId = null;
    }
    renderTierSummary(data);
    renderTierHighlights(data);
    renderTierDetail();
    renderTierBoard(data);
  } catch (err) {
    state.tierData = null;
    $("#tierSummary")?.classList.add("hidden");
    $("#tierHighlights")?.classList.add("hidden");
    $("#tierDetail")?.classList.add("hidden");
    $("#tierBoard").innerHTML = `<p style="color:#fca5a5;padding:16px">${err.message}</p>`;
  }
}

function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".tabs__btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  $("#tabDraft").classList.toggle("hidden", tab !== "draft");
  $("#tabCounters").classList.toggle("hidden", tab !== "counters");
  $("#tabMeta").classList.toggle("hidden", tab !== "meta");
  $("#tabTiers").classList.toggle("hidden", tab !== "tiers");
  $("#tabIngame").classList.toggle("hidden", tab !== "ingame");
  if (tab === "meta") {
    renderMetaRoleFilters();
    fetchMetaTops();
  }
  if (tab === "tiers") {
    renderTierModeFilters();
    renderTierRoleFilters();
    renderTierLaneFilters();
    fetchTierList();
  }
  if (tab === "ingame") {
    renderIngameDraftPreview();
    renderIngameFilters();
    fetchIngameAdvice();
  }
  if (tab === "counters") {
    renderCounterMyRoleFilters();
    renderCounterMyLaneFilters();
    renderCounterQuick();
    renderCounterHeroGrid();
    if (state.counterTargetId) fetchCounterPicks();
  }
}

function renderCounterTarget() {
  const wrap = $("#counterTarget");
  if (!state.counterTargetId) {
    wrap.innerHTML = `
      <div class="counter-target__empty">
        <span>🎯</span>
        <p>Кликните на героя ниже или выберите из драфта</p>
      </div>`;
    return;
  }
  const hero = state.heroesById[state.counterTargetId];
  wrap.innerHTML = `
    <div class="counter-target__hero">
      ${heroPortrait(hero, hero.name, "2xl")}
      <div>
        <div class="counter-target__name">Контрпик против ${hero.name}</div>
        <div style="margin-top:6px">${roleBadge(hero.role)} ${laneLabel(hero.lane)}</div>
      </div>
    </div>`;
}

function renderCounterQuick() {
  const enemies = teamList("enemy");
  const wrap = $("#counterQuick");
  const list = $("#counterQuickList");
  if (!enemies.length) {
    wrap.classList.add("hidden");
    list.innerHTML = "";
    return;
  }
  wrap.classList.remove("hidden");
  list.innerHTML = "";
  enemies.forEach((id) => {
    const hero = state.heroesById[id];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "counter-chip" + (state.counterTargetId === id ? " active" : "");
    btn.innerHTML = `${heroPortrait(hero, hero.name, "xs")}${hero.name}`;
    btn.addEventListener("click", () => selectCounterTarget(id));
    list.appendChild(btn);
  });
}

async function selectCounterTarget(heroId) {
  state.counterTargetId = heroId;
  renderCounterTarget();
  renderCounterQuick();
  renderCounterHeroGrid();
  await fetchCounterPicks();
}

function renderCounterCard(item, rank) {
  return `
    <article class="counter-card">
      <div class="counter-card__rank">#${rank}</div>
      <div class="counter-card__hero">
        ${heroPortrait(item.image, item.hero_name, "md")}
        <div class="counter-card__info">
          <strong>${item.hero_name}</strong>
          <div class="counter-card__meta">
            ${roleBadge(item.role)} ${laneLabel(item.lane)}
            <span class="difficulty difficulty--${item.difficulty}">${item.difficulty_label}</span>
          </div>
        </div>
      </div>
      <div class="counter-card__rate">
        <strong>+${item.counter_percent}%</strong>
        <small>преимущество</small>
      </div>
    </article>
  `;
}

function renderCounterResults(counters, advice) {
  const empty = $("#counterResultsEmpty");
  const list = $("#counterList");
  if (!counters?.length) {
    empty.classList.remove("hidden");
    const hints = [];
    if (state.counterMyRole) hints.push(`роль «${ROLE_LABELS[state.counterMyRole]}»`);
    if (state.counterMyLane) hints.push(`линия «${LANE_LABELS[state.counterMyLane] || state.counterMyLane}»`);
    const filterHint = hints.length ? ` для ${hints.join(", ")}` : "";
    empty.innerHTML = `<p>Контрпики не найдены${filterHint}</p>`;
    list.classList.add("hidden");
    list.innerHTML = "";
  } else {
    empty.classList.add("hidden");
    list.classList.remove("hidden");
    list.innerHTML = counters.map((c, i) => renderCounterCard(c, i + 1)).join("");
  }

  if (advice) {
    renderAdvice(advice, {
      blockId: "counterAdviceBlock",
      tipsId: "counterAdviceTips",
      listId: "counterAdviceList",
    });
    $("#counterAdviceList")?.querySelectorAll(".advice-add").forEach((btn) => {
      btn.addEventListener("click", () => {
        addHero("ally", Number(btn.dataset.heroId));
        switchTab("draft");
      });
    });
  }
}

function renderCounterMyLaneFilters() {
  const wrap = $("#counterMyLaneFilters");
  if (!wrap) return;
  wrap.innerHTML = "";

  const anyLabel = document.createElement("label");
  anyLabel.className = "my-role-check";
  anyLabel.innerHTML = `<input type="checkbox" name="counterMyLane" value="" ${!state.counterMyLane ? "checked" : ""}> <span>Любая линия</span>`;
  anyLabel.querySelector("input").addEventListener("change", (e) => {
    if (e.target.checked) {
      state.counterMyLane = null;
      renderCounterMyLaneFilters();
      if (state.counterTargetId) fetchCounterPicks();
    }
  });
  wrap.appendChild(anyLabel);

  LANES.forEach((lane) => {
    const label = document.createElement("label");
    label.className = "my-role-check";
    const checked = state.counterMyLane === lane.id;
    label.innerHTML = `<input type="checkbox" name="counterMyLane" value="${lane.id}" ${checked ? "checked" : ""}> <span>${lane.label}</span>`;
    label.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) {
        state.counterMyLane = lane.id;
        renderCounterMyLaneFilters();
        if (state.counterTargetId) fetchCounterPicks();
      }
    });
    wrap.appendChild(label);
  });
}

function renderCounterMyRoleFilters() {
  const wrap = $("#counterMyRoleFilters");
  if (!wrap) return;
  wrap.innerHTML = "";

  const anyLabel = document.createElement("label");
  anyLabel.className = "my-role-check";
  anyLabel.innerHTML = `<input type="checkbox" name="counterMyRole" value="" ${!state.counterMyRole ? "checked" : ""}> <span>Любая роль</span>`;
  anyLabel.querySelector("input").addEventListener("change", (e) => {
    if (e.target.checked) {
      state.counterMyRole = null;
      renderCounterMyRoleFilters();
      if (state.counterTargetId) fetchCounterPicks();
    }
  });
  wrap.appendChild(anyLabel);

  PLAYABLE_ROLES.forEach((role) => {
    const label = document.createElement("label");
    label.className = "my-role-check";
    const checked = state.counterMyRole === role;
    label.innerHTML = `<input type="checkbox" name="counterMyRole" value="${role}" ${checked ? "checked" : ""}> <span>${ROLE_LABELS[role]}</span>`;
    label.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) {
        state.counterMyRole = role;
        renderCounterMyRoleFilters();
        if (state.counterTargetId) fetchCounterPicks();
      }
    });
    wrap.appendChild(label);
  });
}

async function fetchCounterPicks() {
  if (!state.counterTargetId) {
    $("#counterResultsEmpty").classList.remove("hidden");
    $("#counterList").classList.add("hidden");
    $("#counterAdviceBlock")?.classList.add("hidden");
    return;
  }
  const exclude = [...teamList("ally"), ...teamList("enemy")].join(",");
  const roleParam = state.counterMyRole ? `&role=${encodeURIComponent(state.counterMyRole)}` : "";
  const laneParam = state.counterMyLane ? `&lane=${encodeURIComponent(state.counterMyLane)}` : "";
  try {
    const data = await api(
      `/api/counters/${state.counterTargetId}?limit=15&exclude=${exclude}${roleParam}${laneParam}`
    );
    renderCounterResults(data.counters, data.advice);
  } catch (err) {
    console.error(err);
  }
}

function mountRoleFilters(containerId, onChange) {
  const wrap = document.getElementById(containerId);
  if (!wrap) return;
  wrap.innerHTML = "";
  ROLES.forEach((role) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip" + (state.roleFilter === role ? " active" : "");
    btn.textContent = ROLE_LABELS[role];
    btn.addEventListener("click", () => {
      state.roleFilter = role;
      onChange();
    });
    wrap.appendChild(btn);
  });
}

function mountLaneFilters(containerId, onChange) {
  const wrap = document.getElementById(containerId);
  if (!wrap) return;
  wrap.innerHTML = "";

  const allLabel = document.createElement("label");
  allLabel.className = "lane-check";
  const allChecked = state.laneFilters.size === 0;
  allLabel.innerHTML = `<input type="checkbox" ${allChecked ? "checked" : ""}> <span>Все линии</span>`;
  allLabel.querySelector("input").addEventListener("change", (e) => {
    if (e.target.checked) {
      state.laneFilters.clear();
      onChange();
    }
  });
  wrap.appendChild(allLabel);

  LANES.forEach((lane) => {
    const label = document.createElement("label");
    label.className = "lane-check";
    const checked = state.laneFilters.has(lane.id);
    label.innerHTML = `<input type="checkbox" ${checked ? "checked" : ""}> <span>${lane.label}</span>`;
    label.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) state.laneFilters.add(lane.id);
      else state.laneFilters.delete(lane.id);
      onChange();
    });
    wrap.appendChild(label);
  });
}

function refreshAllFilters() {
  mountRoleFilters("roleFilters", refreshAllFilters);
  mountLaneFilters("laneFilters", refreshAllFilters);
  mountRoleFilters("counterRoleFilters", refreshAllFilters);
  mountLaneFilters("counterLaneFilters", refreshAllFilters);
  renderHeroGrid();
  renderCounterHeroGrid();
}

function renderCounterHeroGrid() {
  const grid = $("#counterHeroGrid");
  if (!grid) return;
  grid.innerHTML = "";
  const search = ($("#counterSearch")?.value || "").trim().toLowerCase();
  const filtered = state.heroes.filter((h) => heroPassesFilters(h, search));

  filtered.forEach((hero) => {
    const card = document.createElement("div");
    card.className = "hero-card";
    if (state.counterTargetId === hero.id) card.classList.add("selected-enemy");
    card.setAttribute("role", "button");
    card.tabIndex = 0;
    card.innerHTML = `
      ${heroPortrait(hero, hero.name, "lg")}
      <div class="hero-card__meta">${roleBadge(hero.role)}${laneLabel(hero.lane)}</div>
      <div class="hero-card__name">${hero.name}</div>
    `;
    card.addEventListener("click", () => selectCounterTarget(hero.id));
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        selectCounterTarget(hero.id);
      }
    });
    grid.appendChild(card);
  });
}

function renderAll() {
  renderSlots();
  renderHeroGrid();
  renderCounterQuick();
  renderSavedComps();
  renderPickVsSelect();
  renderIngameDraftPreview();
}

async function init() {
  refreshAllFilters();
  renderCounterMyRoleFilters();
  renderCounterMyLaneFilters();
  renderMetaRoleFilters();
  renderSlots();
  renderCounterTarget();

  document.querySelectorAll(".tabs__btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  $("#refreshDataBtn").addEventListener("click", () => startDataRefresh(false));
  $("#refreshDataFullBtn").addEventListener("click", () => {
    if (!confirm("Полное обновление займёт 40–60 минут. Продолжить?")) return;
    startDataRefresh(true);
  });

  $("#heroSearch").addEventListener("input", renderHeroGrid);
  $("#counterSearch")?.addEventListener("input", renderCounterHeroGrid);
  $("#clearBtn").addEventListener("click", clearDraft);
  $("#saveCompBtn")?.addEventListener("click", saveComposition);
  $("#deleteCompBtn")?.addEventListener("click", deleteComposition);
  $("#savedCompSelect")?.addEventListener("change", (e) => {
    if (e.target.value) loadComposition(e.target.value);
  });
  $("#pickVsSelect")?.addEventListener("change", (e) => {
    state.pickVsEnemyId = e.target.value ? Number(e.target.value) : null;
    fetchPickVs();
  });
  $("#analyzeBtn").addEventListener("click", runAnalyze);
  $("#modeSelect").addEventListener("change", runAnalyze);

  $("#pickerClose").addEventListener("click", closePicker);
  $("#pickerOverlay").addEventListener("click", (e) => {
    if (e.target.id === "pickerOverlay") closePicker();
  });
  $("#pickEnemy").addEventListener("click", () => {
    if (state.pendingHero) addHero("enemy", state.pendingHero.id);
    closePicker();
  });
  $("#pickAlly").addEventListener("click", () => {
    if (state.pendingHero) addHero("ally", state.pendingHero.id);
    closePicker();
  });
  $("#pickAllyBan")?.addEventListener("click", () => {
    if (state.pendingHero) addBan("ally", state.pendingHero.id);
    closePicker();
  });
  $("#pickEnemyBan")?.addEventListener("click", () => {
    if (state.pendingHero) addBan("enemy", state.pendingHero.id);
    closePicker();
  });

  try {
    const health = await api("/api/health");
    if (!health.cache_exists) {
      setStatus("Нет кэша данных", "error");
      return;
    }
    setDataUpdated(health.updated_at);
    if (health.refresh?.status === "running") {
      renderRefreshProgress(health.refresh);
      stopRefreshPoll();
      refreshPollTimer = setInterval(pollRefreshStatus, 1500);
    } else {
      setStatus(`${health.heroes} героев загружено`, "ok");
    }

    const { heroes } = await api("/api/heroes");
    state.heroes = heroes;
    state.heroesById = Object.fromEntries(heroes.map((h) => [h.id, h]));
    renderHeroGrid();
    renderCounterHeroGrid();
    renderSavedComps();
    renderPickVsSelect();
    renderIngameFilters();
  } catch (err) {
    setStatus(err.message, "error");
  }
}

init();
