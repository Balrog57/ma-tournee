/* global TourMap */

(function () {
  const state = {
    schools: [],
    selected: new Set(),
    depot: null,
    config: null,
  };

  const els = {
    list: document.getElementById("school-list"),
    search: document.getElementById("search"),
    status: document.getElementById("status-bar"),
    dialog: document.getElementById("school-dialog"),
    form: document.getElementById("school-form"),
    dialogTitle: document.getElementById("dialog-title"),
    dialogError: document.getElementById("dialog-error"),
    btnDelete: document.getElementById("btn-dialog-delete"),
    tourPanel: document.getElementById("tour-panel"),
    tourSummary: document.getElementById("tour-summary"),
    tourStops: document.getElementById("tour-stops"),
    tourWarnings: document.getElementById("tour-warnings"),
    depotForm: document.getElementById("depot-form"),
    depotStatus: document.getElementById("depot-status"),
  };

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
    els.status.textContent = message || "";
    els.status.style.color = isError ? "#9b1c1c" : "";
  }

  function statusLabel(school) {
    const map = {
      ok: "OK",
      pending: "En attente",
      failed: "Introuvable",
      manual: "Manuel",
    };
    return map[school.geocode_status] || school.geocode_status;
  }

  function visibleSchools() {
    const q = (els.search.value || "").trim().toLowerCase();
    if (!q) return state.schools.slice();
    return state.schools.filter(function (s) {
      return (
        (s.name || "").toLowerCase().indexOf(q) !== -1 ||
        (s.address || "").toLowerCase().indexOf(q) !== -1 ||
        (s.phone || "").toLowerCase().indexOf(q) !== -1
      );
    });
  }

  function renderList() {
    const schools = visibleSchools();
    els.list.innerHTML = "";
    if (!schools.length) {
      const empty = document.createElement("p");
      empty.className = "hint";
      empty.style.padding = "0.75rem";
      empty.textContent = "Aucune école.";
      els.list.appendChild(empty);
      return;
    }
    schools.forEach(function (school) {
      const item = document.createElement("div");
      item.className = "school-item";
      item.setAttribute("role", "listitem");

      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = state.selected.has(school.id);
      check.addEventListener("change", function () {
        if (check.checked) state.selected.add(school.id);
        else state.selected.delete(school.id);
        refreshMap();
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
      if (school.geocode_error) {
        const err = document.createElement("p");
        err.className = "warn";
        err.textContent = school.geocode_error;
        meta.appendChild(err);
      }

      const side = document.createElement("div");
      side.className = "item-actions";
      const badge = document.createElement("span");
      badge.className = "badge " + school.geocode_status;
      badge.textContent = statusLabel(school);
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn ghost";
      editBtn.textContent = "Modifier";
      editBtn.addEventListener("click", function () {
        openSchoolDialog(school);
      });
      const geoBtn = document.createElement("button");
      geoBtn.type = "button";
      geoBtn.className = "btn ghost";
      geoBtn.textContent = "Géocoder";
      geoBtn.addEventListener("click", async function () {
        try {
          setStatus("Géocodage…");
          await api("/api/schools/" + school.id + "/geocode", { method: "POST" });
          await loadSchools();
          setStatus("Géocodage terminé");
        } catch (err) {
          setStatus(err.message, true);
        }
      });
      side.appendChild(badge);
      side.appendChild(editBtn);
      side.appendChild(geoBtn);

      item.appendChild(check);
      item.appendChild(meta);
      item.appendChild(side);
      els.list.appendChild(item);
    });
  }

  function refreshMap() {
    TourMap.setDepot(state.depot);
    TourMap.setSchools(state.schools, Array.from(state.selected));
  }

  async function loadConfig() {
    state.config = await api("/api/config");
    TourMap.init(state.config);
  }

  async function loadDepot() {
    state.depot = await api("/api/settings/depot");
    const form = els.depotForm;
    form.name.value = state.depot.name || "";
    form.address.value = state.depot.address || "";
    form.lat.value = state.depot.lat != null ? state.depot.lat : "";
    form.lon.value = state.depot.lon != null ? state.depot.lon : "";
    els.depotStatus.textContent =
      "Statut: " +
      (state.depot.geocode_status || "?") +
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

  function openSchoolDialog(school) {
    els.dialogError.textContent = "";
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
  document.getElementById("btn-new").addEventListener("click", function () {
    openSchoolDialog(null);
  });

  document.getElementById("btn-dialog-cancel").addEventListener("click", function () {
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

  els.btnDelete.addEventListener("click", async function () {
    const id = els.form.id.value;
    if (!id) return;
    if (!window.confirm("Supprimer cette école ?")) return;
    try {
      await api("/api/schools/" + id, { method: "DELETE" });
      state.selected.delete(Number(id));
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
      state.depot = await api("/api/settings/depot/geocode", { method: "POST" });
      await loadDepot();
      refreshMap();
      setStatus("Dépôt géocodé");
    } catch (err) {
      setStatus(err.message, true);
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
