/* global L */

window.TourMap = (function () {
  let map = null;
  let tileLayer = null;
  let schoolLayer = null;
  let routeLayer = null;
  let depotMarker = null;
  const schoolMarkers = new Map();

  function init(config) {
    map = L.map("map", {
      zoomControl: true,
      attributionControl: true,
    }).setView([config.map_center_lat, config.map_center_lon], config.map_default_zoom);

    tileLayer = L.tileLayer(config.tile_url, {
      maxZoom: 19,
      attribution: config.tile_attribution,
    });
    tileLayer.on("tileerror", function () {
      // Fond optionnel : les marqueurs restent visibles
    });
    tileLayer.addTo(map);

    schoolLayer = L.layerGroup().addTo(map);
    routeLayer = L.layerGroup().addTo(map);

    // Icônes locales (pas de CDN)
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: "/static/vendor/leaflet/images/marker-icon-2x.png",
      iconUrl: "/static/vendor/leaflet/images/marker-icon.png",
      shadowUrl: "/static/vendor/leaflet/images/marker-shadow.png",
    });
  }

  function setDepot(depot) {
    if (depotMarker) {
      map.removeLayer(depotMarker);
      depotMarker = null;
    }
    if (depot && depot.lat != null && depot.lon != null) {
      depotMarker = L.circleMarker([depot.lat, depot.lon], {
        radius: 9,
        color: "#6e1d2c",
        fillColor: "#6e1d2c",
        fillOpacity: 0.92,
        weight: 2,
      })
        .bindPopup("<strong>" + escapeHtml(depot.name) + "</strong><br>" + escapeHtml(depot.address))
        .addTo(map);
    }
  }

  function setSchools(schools, selectedIds) {
    schoolLayer.clearLayers();
    schoolMarkers.clear();
    const selected = new Set(selectedIds || []);
    schools.forEach(function (school) {
      if (school.lat == null || school.lon == null) return;
      const selectedStyle = selected.has(school.id);
      const marker = L.circleMarker([school.lat, school.lon], {
        radius: selectedStyle ? 8 : 6,
        color: selectedStyle ? "#4a121c" : "#8b3a48",
        fillColor: selectedStyle ? "#6e1d2c" : "#c89aa3",
        fillOpacity: 0.88,
        weight: selectedStyle ? 3 : 1,
      }).bindPopup(
        "<strong>" +
          escapeHtml(school.name) +
          "</strong><br>" +
          escapeHtml(school.address)
      );
      marker.addTo(schoolLayer);
      schoolMarkers.set(school.id, marker);
    });
  }

  function setRoute(geometry, fit) {
    routeLayer.clearLayers();
    if (!geometry || !geometry.coordinates || !geometry.coordinates.length) return;
    const latlngs = geometry.coordinates.map(function (c) {
      return [c[1], c[0]];
    });
    const line = L.polyline(latlngs, {
      color: "#6e1d2c",
      weight: 4,
      opacity: 0.92,
    }).addTo(routeLayer);
    if (fit) {
      map.fitBounds(line.getBounds(), { padding: [30, 30] });
    }
  }

  function clearRoute() {
    routeLayer.clearLayers();
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  return {
    init: init,
    setDepot: setDepot,
    setSchools: setSchools,
    setRoute: setRoute,
    clearRoute: clearRoute,
    escapeHtml: escapeHtml,
  };
})();
