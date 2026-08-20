/* global L */

window.TourMap = (function () {
  let map = null;
  let tileLayer = null;
  let schoolLayer = null;
  let routeLayer = null;
  let depotMarker = null;
  let onSchoolClick = null;
  const schoolMarkers = new Map();

  const STAR_SVG =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">' +
    '<polygon points="12,2 14.9,8.6 22,9.3 16.8,14.2 18.2,21.3 12,17.8 5.8,21.3 7.2,14.2 2,9.3 9.1,8.6" ' +
    'fill="#d4a017" stroke="#4a121c" stroke-width="1.4" stroke-linejoin="round"/>' +
    "</svg>";

  function init(config, options) {
    options = options || {};
    onSchoolClick = options.onSchoolClick || null;
    map = L.map("map", {
      zoomControl: true,
      attributionControl: true,
    }).setView([config.map_center_lat, config.map_center_lon], config.map_default_zoom);

    tileLayer = L.tileLayer(config.tile_url, {
      maxZoom: 19,
      attribution: config.tile_attribution,
    });
    tileLayer.on("tileerror", function () {});
    tileLayer.addTo(map);

    schoolLayer = L.layerGroup().addTo(map);
    routeLayer = L.layerGroup().addTo(map);

    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: "/static/vendor/leaflet/images/marker-icon-2x.png",
      iconUrl: "/static/vendor/leaflet/images/marker-icon.png",
      shadowUrl: "/static/vendor/leaflet/images/marker-shadow.png",
    });
  }

  function schoolPopupHtml(school) {
    return (
      "<strong>" +
      escapeHtml(school.name) +
      "</strong><br>" +
      escapeHtml(school.city || "") +
      (school.city ? "<br>" : "") +
      escapeHtml(school.address)
    );
  }

  function bindSchoolClick(marker, schoolId) {
    marker.on("click", function () {
      if (typeof onSchoolClick === "function") {
        onSchoolClick(schoolId);
      }
    });
  }

  function favoriteIcon() {
    return L.divIcon({
      className: "school-marker-star",
      html: STAR_SVG,
      iconSize: [22, 22],
      iconAnchor: [11, 11],
      popupAnchor: [0, -12],
    });
  }

  function setDepot(depot) {
    if (depotMarker) {
      map.removeLayer(depotMarker);
      depotMarker = null;
    }
    if (depot && depot.lat != null && depot.lon != null) {
      depotMarker = L.circleMarker([depot.lat, depot.lon], {
        radius: 11,
        color: "#2e0a12",
        fillColor: "#6e1d2c",
        fillOpacity: 1,
        weight: 3,
      })
        .bindPopup(
          "<strong>" +
            escapeHtml(depot.name) +
            "</strong><br>" +
            escapeHtml(depot.address)
        )
        .addTo(map);
    }
  }

  function focusDepot(depot) {
    if (!depot || depot.lat == null || depot.lon == null || !map) return;
    map.setView([depot.lat, depot.lon], Math.max(map.getZoom(), 15), { animate: true });
    if (depotMarker) depotMarker.openPopup();
  }

  function setSchools(schools, selectedIds) {
    schoolLayer.clearLayers();
    schoolMarkers.clear();
    const selected = new Set(selectedIds || []);
    schools.forEach(function (school) {
      if (school.lat == null || school.lon == null) return;
      const selectedStyle = selected.has(school.id);
      const favorite = !!school.favorite;
      let marker;

      if (selectedStyle) {
        marker = L.circleMarker([school.lat, school.lon], {
          radius: 11,
          color: "#f7ebea",
          fillColor: "#2e0a12",
          fillOpacity: 1,
          weight: 3,
        });
      } else if (favorite) {
        marker = L.marker([school.lat, school.lon], {
          icon: favoriteIcon(),
          riseOnHover: true,
        });
      } else {
        marker = L.circleMarker([school.lat, school.lon], {
          radius: 8,
          color: "#4a121c",
          fillColor: "#e8b4bc",
          fillOpacity: 0.95,
          weight: 2,
        });
      }

      marker.bindPopup(schoolPopupHtml(school));
      bindSchoolClick(marker, school.id);
      marker.addTo(schoolLayer);
      schoolMarkers.set(school.id, marker);
    });
  }

  function focusSchool(school) {
    if (!school || school.lat == null || school.lon == null || !map) return;
    map.setView([school.lat, school.lon], Math.max(map.getZoom(), 14), { animate: true });
    const marker = schoolMarkers.get(school.id);
    if (marker) marker.openPopup();
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
    focusSchool: focusSchool,
    focusDepot: focusDepot,
    escapeHtml: escapeHtml,
  };
})();
