/* global TourMap */

(function () {
  const state = {
    schools: [],
    selected: new Set(),
    depot: null,
    config: null,
  };

  const els = {
    layout: document.querySelector(".layout"),
    list: document.getElementById("school-list"),
    btnToggleList: document.getElementById("btn-toggle-list"),
    search: document.getElementById("search"),
    status: document.getElementById("status-bar"),
    dialog: document.getElementById("school-dialog"),
    form: document.getElementById("school-form"),
    dialogTitle: document.getElementById("dialog-title"),
    dialogError: document.getElementById("dialog-error"),
    btnDelete: document.getElementById("btn-dialog-delete"),
    deleteConfirm: document.getElementById("delete-confirm"),
    deleteConfirmName: document.getElementById("delete-confirm-name"),
    btnDeleteYes: document.getElementById("btn-delete-yes"),
    btnDeleteNo: document.getElementById("btn-delete-no"),
    tourPanel: document.getElementById("tour-panel"),
    tourSummary: document.getElementById("tour-summary"),
    tourStops: document.getElementById("tour-stops"),
    tourWarnings: document.getElementById("tour-warnings"),
    depotForm: document.getElementById("depot-form"),
    depotStatus: document.getElementById("depot-status"),
    depotSummary: document.getElementById("depot-summary"),
  };

  let statusTimer = null;

  function escapeHtml(value) {
    return TourMap.escapeHtml(value);
  }

  async function api(path, options) {
    const opts = options || {};
    const headers = Object.assign({}, opts.headers || {});
    if (opts.body && !(opts.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch(
      path,
      Object.assign({ credentials: "same-origin" }, opts, { headers: headers })
    );
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Authentification requise");
    }
    if (response.status === 204) return null;
    const text = await response.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (e) {
        data = { detail: text };
      }
    }
    if (!response.ok) {
      const detail = data && data.detail ? formatDetail(data.detail) : "Erreur réseau";
      throw new Error(detail);
    }
    return data;
  }

  function formatDetail(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map(function (item) {
          return item.msg || JSON.stringify(item);
        })
        .join(" ; ");
    }
    return JSON.stringify(detail);
  }

  function setStatus(message, isError) {
    clearTimeout(statusTimer);
    if (!els.status) return;
    els.status.textContent = message || "";
    els.status.classList.toggle("is-error", !!isError);
    els.status.classList.toggle("visible", !!message);
    if (message) {
      statusTimer = setTimeout(function () {
        els.status.classList.remove("visible");
      }, isError ? 6000 : 3500);
    }
  }

  function updateDepotSummary() {
    if (!els.depotSummary) return;
    const name = (els.depotForm.name.value || "").trim();
    els.depotSummary.textContent = name ? "Dépôt — " + name : "Dépôt";
  }

  function statusLabel(school) {
    const map = {
      ok: "Sur la carte",
      pending: "À localiser",
      failed: "Pas sur la carte",
      manual: "Position manuelle",
    };
    return map[school.geocode_status] || school.geocode_status;
  }

  function statusTitle(school) {
    const map = {
      ok: "Cette école apparaît déjà sur la carte.",
      pending: "L'adresse n'a pas encore été localisée.",
      failed: "L'adresse n'a pas pu être trouvée automatiquement.",
      manual: "Les coordonnées ont été saisies à la main (sans recherche automatique).",
    };
    return map[school.geocode_status] || "";
  }

  function updateSelectionCount() {
    const el = document.getElementById("selection-count");
    if (!el) return;
    const n = state.selected.size;
    const num = el.querySelector(".count-num");
    if (num) num.textContent = String(n);
    else el.textContent = "Sélec. " + n;
    el.classList.toggle("has-selection", n > 0);
    el.title =
      n === 0
        ? "Aucune école sélectionnée pour la tournée"
        : n === 1
          ? "1 école sélectionnée pour la tournée"
          : n + " écoles sélectionnées pour la tournée";
  }

  function visibleSchools() {
    const q = normalizeSearch(els.search.value);
    if (!q) return state.schools.slice();
    return state.schools.filter(function (s) {
      return (
        normalizeSearch(s.name).indexOf(q) !== -1 ||
        normalizeSearch(s.address).indexOf(q) !== -1 ||
        normalizeSearch(s.city).indexOf(q) !== -1 ||
        normalizeSearch(s.phone).indexOf(q) !== -1
      );
    });
  }

  function normalizeSearch(value) {
    return String(value || "")
      .replace(/[œŒ]/g, "oe")
      .replace(/[æÆ]/g, "ae")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("fr-FR");
  }

  function setListCollapsed(collapsed) {
    els.layout.classList.toggle("list-collapsed", collapsed);
    els.btnToggleList.setAttribute("aria-expanded", String(!collapsed));
    els.btnToggleList.textContent = collapsed ? "☰ Liste" : "× Liste";
    requestAnimationFrame(function () {
      window.dispatchEvent(new Event("resize"));
    });
  }

  function selectSchoolFromMap(schoolId) {
    setListCollapsed(false);
    requestAnimationFrame(function () {
      const row = els.list.querySelector('[data-school-id="' + schoolId + '"]');
      if (!row) return;
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      row.classList.add("flash");
      setTimeout(function () {
        row.classList.remove("flash");
      }, 1200);
    });
    const school = state.schools.find(function (s) {
      return s.id === schoolId;
    });
    if (school) {
      TourMap.focusSchool(school);
    }
  }

  function renderList() {
    const schools = visibleSchools();
    els.list.innerHTML = "";
    updateSelectionCount();
    if (!schools.length) {
      const empty = document.createElement("p");
      empty.className = "hint";
      empty.style.padding = "0.75rem";
      empty.textContent = "Aucune école.";
      els.list.appendChild(empty);
      return;
    }

    let lastCity = null;
    let inFavorites = null;
    schools.forEach(function (school) {
      const isFav = !!school.favorite;
      if (isFav !== inFavorites) {
        inFavorites = isFav;
        lastCity = null;
        if (isFav) {
          const favHeader = document.createElement("div");
          favHeader.className = "city-header favorites-header";
          favHeader.textContent = "Favoris";
          els.list.appendChild(favHeader);
        }
      }
      const city = (school.city || "Autre").trim() || "Autre";
      if (city !== lastCity) {
        lastCity = city;
        const header = document.createElement("div");
        header.className = "city-header";
        header.textContent = city;
        els.list.appendChild(header);
      }

      const item = document.createElement("div");
      item.className = "school-item" + (state.selected.has(school.id) ? " selected" : "");
      item.dataset.schoolId = String(school.id);
      item.setAttribute("role", "listitem");

      const check = document.createElement("input");
      check.type = "checkbox";
      check.className = "school-check";
      check.title = "Inclure dans la tournée";
      check.checked = state.selected.has(school.id);
      check.addEventListener("change", function () {
        if (check.checked) state.selected.add(school.id);
        else state.selected.delete(school.id);
        item.classList.toggle("selected", check.checked);
        refreshMap();
        updateSelectionCount();
      });

      const star = document.createElement("button");
      star.type = "button";
      star.className = "star-btn" + (school.favorite ? " active" : "");
      star.title = school.favorite ? "Retirer des favoris" : "Ajouter aux favoris";
      star.setAttribute("aria-label", star.title);
      star.textContent = school.favorite ? "★" : "☆";
      star.addEventListener("click", async function (event) {
        event.stopPropagation();
        try {
          await api("/api/schools/" + school.id, {
            method: "PUT",
            body: JSON.stringify({ favorite: !school.favorite }),
          });
          await loadSchools();
        } catch (err) {
          setStatus(err.message, true);
        }
      });

      const meta = document.createElement("div");
      meta.className = "meta";
      const name = document.createElement("p");
      name.className = "name";
      name.textContent = school.name;
      const addr = document.createElement("p");
      addr.className = "addr";
      addr.textContent = school.address;
      meta.appendChild(name);
      meta.appendChild(addr);
      if (school.phone) {
        const phone = document.createElement("p");
        phone.className = "phone";
        phone.textContent = school.phone;
        meta.appendChild(phone);
      }
      if (school.geocode_error && school.geocode_status === "failed") {
        const err = document.createElement("p");
        err.className = "warn";
        err.textContent = school.geocode_error;
        meta.appendChild(err);
      }

      const side = document.createElement("div");
      side.className = "item-actions";

      if (school.geocode_status !== "ok") {
        const badge = document.createElement("span");
        badge.className = "badge " + school.geocode_status;
        badge.textContent = statusLabel(school);
        badge.title = statusTitle(school);
        side.appendChild(badge);
      }

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn ghost";
      editBtn.textContent = "Modifier";
      editBtn.addEventListener("click", function (event) {
        event.stopPropagation();
        openSchoolDialog(school);
      });
      side.appendChild(editBtn);

      if (school.geocode_status === "failed" || school.geocode_status === "pending") {
        const geoBtn = document.createElement("button");
        geoBtn.type = "button";
        geoBtn.className = "btn ghost";
        geoBtn.textContent = "Localiser";
        geoBtn.title =
          "Cherche automatiquement la position de l'adresse pour l'afficher sur la carte";
        geoBtn.addEventListener("click", async function (event) {
          event.stopPropagation();
          try {
            setStatus("Localisation de l'adresse…");
            await api("/api/schools/" + school.id + "/geocode", { method: "POST" });
            await loadSchools();
            setStatus("Position trouvée");
          } catch (err) {
            setStatus(err.message, true);
          }
        });
        side.appendChild(geoBtn);
      }

      item.appendChild(check);
      item.appendChild(star);
      item.appendChild(meta);
      item.appendChild(side);

      item.addEventListener("click", function (event) {
        if (
          event.target === check ||
          event.target === star ||
          event.target.closest("button") ||
          event.target.closest(".badge")
        ) {
          return;
        }
        check.checked = !check.checked;
        check.dispatchEvent(new Event("change"));
      });

      els.list.appendChild(item);
    });
  }

  function refreshMap() {
    TourMap.setDepot(state.depot);
    TourMap.setSchools(state.schools, Array.from(state.selected));
  }

  async function loadConfig() {
    state.config = await api("/api/config");
    TourMap.init(state.config, { onSchoolClick: selectSchoolFromMap });
  }

  async function loadDepot() {
    state.depot = await api("/api/settings/depot");
    const form = els.depotForm;
    form.name.value = state.depot.name || "";
    form.address.value = state.depot.address || "";
    form.lat.value = state.depot.lat != null ? state.depot.lat : "";
    form.lon.value = state.depot.lon != null ? state.depot.lon : "";
    updateDepotSummary();
    els.depotStatus.textContent =
      (state.depot.geocode_status === "ok"
        ? "Dépôt localisé sur la carte"
        : state.depot.geocode_status === "manual"
          ? "Position du dépôt réglée à la main"
          : state.depot.geocode_status === "failed"
            ? "Adresse du dépôt non trouvée"
            : "Dépôt à localiser") +
      (state.depot.geocode_error ? " — " + state.depot.geocode_error : "");
  }

  async function loadSchools() {
    const q = (els.search.value || "").trim();
    const path = q ? "/api/schools?q=" + encodeURIComponent(q) : "/api/schools";
    state.schools = await api(path);
    const ids = new Set(state.schools.map(function (s) { return s.id; }));
    state.selected.forEach(function (id) {
      if (!ids.has(id)) state.selected.delete(id);
    });
    renderList();
    refreshMap();
  }

  async function loadHealth() {
    try {
      const health = await fetch("/health").then(function (r) { return r.json(); });
      const parts = [];
      parts.push(health.status === "ok" ? "Système OK" : "Mode dégradé");
      if (!health.geocoder) parts.push("géocodeur indisponible");
      if (!health.router) parts.push("itinéraires indisponibles");
      setStatus(parts.join(" — "));
    } catch (e) {
      setStatus("Impossible de joindre /health", true);
    }
  }

  function hideDeleteConfirm() {
    if (els.deleteConfirm) els.deleteConfirm.classList.add("hidden");
    if (els.deleteConfirmName) els.deleteConfirmName.textContent = "";
  }

  function showDeleteConfirm() {
    const name = (els.form.name.value || "").trim() || "cette école";
    els.deleteConfirmName.textContent = name;
    els.deleteConfirm.classList.remove("hidden");
    els.dialogError.textContent = "";
  }

  function openSchoolDialog(school) {
    els.dialogError.textContent = "";
    hideDeleteConfirm();
    els.form.reset();
    if (school) {
      els.dialogTitle.textContent = "Modifier l'école";
      els.form.id.value = school.id;
      els.form.name.value = school.name;
      els.form.address.value = school.address;
      els.form.phone.value = school.phone || "";
      els.form.lat.value = school.lat != null ? school.lat : "";
      els.form.lon.value = school.lon != null ? school.lon : "";
      els.btnDelete.classList.remove("hidden");
    } else {
      els.dialogTitle.textContent = "Nouvelle école";
      els.form.id.value = "";
      els.btnDelete.classList.add("hidden");
    }
    els.dialog.showModal();
  }

  function formatKm(meters) {
    return (meters / 1000).toFixed(1).replace(".", ",") + " km";
  }

  function formatDuration(seconds) {
    const total = Math.round(seconds / 60);
    const h = Math.floor(total / 60);
    const m = total % 60;
    if (h > 0) return h + " h " + m + " min";
    return m + " min";
  }

  function showTour(result) {
    els.tourPanel.classList.remove("hidden");
    els.tourSummary.textContent =
      "Distance " +
      formatKm(result.distance_m) +
      " — Temps " +
      formatDuration(result.duration_s) +
      " — Mode " +
      result.mode;
    els.tourStops.innerHTML = "";
    result.stops.forEach(function (stop) {
      const li = document.createElement("li");
      li.textContent = stop.name + " — " + stop.address;
      els.tourStops.appendChild(li);
    });
    els.tourWarnings.textContent = (result.warnings || []).join(" ");
    TourMap.setRoute(result.geometry, true);
  }

  // Events
  els.btnToggleList.addEventListener("click", function () {
    setListCollapsed(!els.layout.classList.contains("list-collapsed"));
  });

  document.getElementById("btn-new").addEventListener("click", function () {
    openSchoolDialog(null);
  });

  document.getElementById("btn-dialog-cancel").addEventListener("click", function () {
    hideDeleteConfirm();
    els.dialog.close();
  });

  document.getElementById("btn-select-visible").addEventListener("click", function () {
    visibleSchools().forEach(function (s) { state.selected.add(s.id); });
    renderList();
    refreshMap();
  });

  document.getElementById("btn-clear-selection").addEventListener("click", function () {
    state.selected.clear();
    renderList();
    refreshMap();
    TourMap.clearRoute();
    els.tourPanel.classList.add("hidden");
    updateSelectionCount();
  });

  let searchTimer = null;
  els.search.addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () {
      loadSchools().catch(function (err) { setStatus(err.message, true); });
    }, 250);
  });

  els.form.addEventListener("submit", async function (event) {
    event.preventDefault();
    els.dialogError.textContent = "";
    const id = els.form.id.value;
    const payload = {
      name: els.form.name.value.trim(),
      address: els.form.address.value.trim(),
      phone: els.form.phone.value.trim() || null,
    };
    const lat = els.form.lat.value.trim();
    const lon = els.form.lon.value.trim();
    if (lat !== "" && lon !== "") {
      payload.lat = Number(lat);
      payload.lon = Number(lon);
    }
    try {
      if (id) {
        await api("/api/schools/" + id, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        await api("/api/schools", { method: "POST", body: JSON.stringify(payload) });
      }
      els.dialog.close();
      await loadSchools();
      setStatus("École enregistrée");
    } catch (err) {
      els.dialogError.textContent = err.message;
    }
  });

  els.btnDelete.addEventListener("click", function () {
    const id = els.form.id.value;
    if (!id) return;
    showDeleteConfirm();
  });

  els.btnDeleteNo.addEventListener("click", function () {
    hideDeleteConfirm();
  });

  els.btnDeleteYes.addEventListener("click", async function () {
    const id = els.form.id.value;
    if (!id) return;
    try {
      await api("/api/schools/" + id, { method: "DELETE" });
      state.selected.delete(Number(id));
      hideDeleteConfirm();
      els.dialog.close();
      await loadSchools();
      setStatus("École supprimée");
    } catch (err) {
      els.dialogError.textContent = err.message;
    }
  });

  document.getElementById("import-file").addEventListener("change", async function (event) {
    const file = event.target.files && event.target.files[0];
    event.target.value = "";
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    try {
      setStatus("Import en cours…");
      const result = await api("/api/schools/import", { method: "POST", body: body });
      await loadSchools();
      setStatus(
        "Import: " +
          result.created +
          " créées, " +
          result.updated +
          " mises à jour, " +
          result.skipped +
          " ignorées"
      );
      if (result.errors && result.errors.length) {
        window.alert(result.errors.slice(0, 10).join("\n"));
      }
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  document.getElementById("btn-optimize").addEventListener("click", async function () {
    const ids = Array.from(state.selected);
    if (!ids.length) {
      setStatus("Sélectionnez au moins une école", true);
      return;
    }
    try {
      setStatus("Calcul de la tournée…");
      const result = await api("/api/tours/optimize", {
        method: "POST",
        body: JSON.stringify({
          school_ids: ids,
          round_trip: document.getElementById("round-trip").checked,
        }),
      });
      showTour(result);
      setStatus("Tournée calculée (" + result.mode + ")");
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  els.depotForm.name.addEventListener("input", updateDepotSummary);

  els.depotForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    const payload = {
      name: els.depotForm.name.value.trim(),
      address: els.depotForm.address.value.trim(),
    };
    const lat = els.depotForm.lat.value.trim();
    const lon = els.depotForm.lon.value.trim();
    if (lat !== "" && lon !== "") {
      payload.lat = Number(lat);
      payload.lon = Number(lon);
    }
    try {
      state.depot = await api("/api/settings/depot", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      await loadDepot();
      refreshMap();
      setStatus("Dépôt enregistré");
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  document.getElementById("btn-geocode-depot").addEventListener("click", async function () {
    try {
      setStatus("Localisation du dépôt…");
      state.depot = await api("/api/settings/depot/geocode", { method: "POST" });
      await loadDepot();
      refreshMap();
      TourMap.focusDepot(state.depot);
      setStatus("Dépôt localisé sur la carte");
    } catch (err) {
      setStatus(err.message, true);
    }
  });

  document.getElementById("btn-copy-phone").addEventListener("click", async function () {
    const btn = document.getElementById("btn-copy-phone");
    const phone = (btn.getAttribute("data-phone") || btn.textContent || "").trim();
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(phone);
      } else {
        const ta = document.createElement("textarea");
        ta.value = phone;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      btn.classList.add("copied");
      btn.textContent = "Copié !";
      setTimeout(function () {
        btn.classList.remove("copied");
        btn.textContent = "Tél. " + phone;
      }, 1600);
    } catch (e) {
      setStatus("Impossible de copier le numéro", true);
    }
  });

  document.getElementById("btn-logout").addEventListener("click", async function () {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch (e) {
      // redirection même en cas d'erreur
    }
    window.location.href = "/login";
  });

  async function boot() {
    try {
      await loadConfig();
      await loadDepot();
      await loadSchools();
      await loadHealth();
      // Leaflet a besoin d'un invalidateSize après layout mobile
      setTimeout(function () {
        window.dispatchEvent(new Event("resize"));
      }, 200);
    } catch (err) {
      setStatus(err.message, true);
    }
  }

  boot();
})();
