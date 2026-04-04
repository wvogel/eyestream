// Apply saved per_page if not in URL
(function () {
  var params = new URLSearchParams(window.location.search);
  if (!params.has("per_page")) {
    var saved = localStorage.getItem("eyestream-per-page");
    if (saved !== null && saved !== "" && saved !== "10") {
      params.set("per_page", saved);
      window.location.search = params.toString();
      return;
    }
  }
})();

var toastTimer = null;

function updateProgress(id, d) {
  var bar = document.getElementById("encode-progress-" + id);
  var statusLine = document.getElementById("encode-status-" + id);
  var posterBox = document.getElementById("video-poster-" + id);

  if (bar && typeof d.progress === "number") bar.style.width = d.progress + "%";
  if (bar) {
    if (d.status === "encoding") bar.classList.add("flame-progress", "is-animating");
    else bar.classList.remove("is-animating");
  }

  if (posterBox) {
    var encodingOverlay = posterBox.querySelector(".video-encoding-overlay");
    if (d.status === "queued" || d.status === "encoding") {
      if (!encodingOverlay) { encodingOverlay = document.createElement("div"); encodingOverlay.className = "video-encoding-overlay"; posterBox.appendChild(encodingOverlay); }
      encodingOverlay.innerText = d.status === "queued" ? T("video.status_queued") : T("video.status_encoding");
    } else if (encodingOverlay) { encodingOverlay.remove(); }

    var cpuFlame = posterBox.querySelector(".cpu-flame-overlay");
    if (d.status === "encoding" && typeof d.cpu_percent === "number") {
      if (!cpuFlame) { cpuFlame = document.createElement("div"); cpuFlame.className = "cpu-flame-overlay"; cpuFlame.innerHTML = '<span class="cpu-flame-label"></span>'; posterBox.appendChild(cpuFlame); }
      cpuFlame.style.height = Math.max(8, d.cpu_percent) + "%";
      cpuFlame.querySelector(".cpu-flame-label").innerText = "CPU " + d.cpu_percent + "%";
    } else if (cpuFlame) { cpuFlame.remove(); }

    if (d.poster_url) {
      var img = posterBox.querySelector("img");
      if (!img) { img = document.createElement("img"); img.alt = T("video.poster_alt"); img.loading = "lazy"; posterBox.prepend(img); }
      if (img.src !== d.poster_url) img.src = d.poster_url;
      var ph = document.getElementById("video-poster-placeholder-" + id);
      if (ph) ph.remove();
    }

    if (d.poster_url && d.playlist_url) {
      posterBox.classList.add("is-playable");
      posterBox.dataset.id = String(id);
      posterBox.dataset.src = d.playlist_url;
      posterBox.dataset.poster = d.poster_url;
      posterBox.onclick = function () { loadPlayer(posterBox); };
      if (!posterBox.querySelector(".play-overlay")) { var ov = document.createElement("div"); ov.className = "play-overlay"; ov.innerText = "\u25b6"; posterBox.appendChild(ov); }
    }
  }

  if (statusLine) {
    if (d.status === "queued") statusLine.innerText = "\u25cf " + T("video.status_waiting_full");
    else if (typeof d.progress === "number") {
      var text = "\u25cf " + T("video.status_encoding") + " " + d.progress + "%";
      if (typeof d.eta_seconds === "number" && d.eta_seconds > 0) {
        text += " \u00b7 ETA " + Math.floor(d.eta_seconds / 60) + ":" + String(Math.floor(d.eta_seconds % 60)).padStart(2, "0");
      }
      statusLine.innerText = text;
    }
  }
}

function watchProgress(id) {
  var es = new EventSource("/events/" + id);
  es.onmessage = function (e) {
    var d = JSON.parse(e.data);
    updateProgress(id, d);
    if (d.status !== "queued" && d.status !== "encoding") {
      es.close();
      // Encoding finished — reload to get final renditions/URLs
      location.reload();
    }
  };
  es.onerror = function () {
    es.close();
    setTimeout(function () { watchProgress(id); }, 10000);
  };
}

function cancelEncode(btn, id) {
  var isConfirming = btn.dataset.confirmingCancel === "1";

  if (!isConfirming) {
    btn.dataset.confirmingCancel = "1";
    btn.dataset.originalText = btn.innerText;
    btn.innerText = T("confirm.cancel_reencode");

    clearTimeout(btn._confirmCancelTimer);
    btn._confirmCancelTimer = setTimeout(function () {
      btn.dataset.confirmingCancel = "0";
      btn.innerText = btn.dataset.originalText || T("button.cancel");
    }, 3500);
    return;
  }

  btn.disabled = true;
  clearTimeout(btn._confirmCancelTimer);
  fetch("/cancel/" + id, { method: "POST" })
    .then(function () {
      showToast(T("toast.reencode_cancelled"), "info");
      // Remove encoding UI from card
      var card = document.querySelector('.video-card[data-id="' + id + '"]');
      if (card) {
        var statusBlock = card.querySelector(".video-status-block");
        if (statusBlock) statusBlock.innerHTML = "";
        var overlay = card.querySelector(".video-encoding-overlay");
        if (overlay) overlay.remove();
        var flame = card.querySelector(".cpu-flame-overlay");
        if (flame) flame.remove();
      }
      location.reload();
    });
}

function toggleDisabled(id, btn) {
  if (btn.dataset.confirming !== "1") {
    btn.dataset.confirming = "1";
    btn.dataset.originalText = btn.innerText;
    btn.innerText = btn.innerText === T("button.deactivate") ? T("confirm.really_deactivate") : T("confirm.really_activate");
    clearTimeout(btn._ct);
    btn._ct = setTimeout(function () {
      btn.dataset.confirming = "0";
      btn.innerText = btn.dataset.originalText;
    }, 3500);
    return;
  }
  btn.disabled = true;
  clearTimeout(btn._ct);
  fetch("/video/" + id + "/toggle-disabled", { method: "POST" })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var card = document.querySelector('.video-card[data-id="' + id + '"]');
      if (card) {
        card.classList.toggle("is-disabled", data.disabled);
        // Update overlay
        var posterBox = document.getElementById("video-poster-" + id);
        if (posterBox) {
          var overlay = posterBox.querySelector(".video-disabled-overlay");
          if (data.disabled && !overlay) {
            overlay = document.createElement("div");
            overlay.className = "video-disabled-overlay";
            overlay.innerText = T("video.status_disabled");
            posterBox.appendChild(overlay);
          } else if (!data.disabled && overlay) {
            overlay.remove();
          }
        }
      }
      // Update button
      btn.disabled = false;
      btn.dataset.confirming = "0";
      btn.innerText = data.disabled ? T("button.activate") : T("button.deactivate");
      btn.classList.toggle("is-disabled-toggle", data.disabled);
      showToast(data.disabled ? T("toast.video_deactivated") : T("toast.video_activated"), data.disabled ? "info" : "success");
    })
    .catch(function () {
      showToast(T("toast.error"), "error");
      btn.disabled = false;
    });
}

function reencode(id, btn) {
  btn.disabled = true;
  fetch("/reencode/" + id, { method: "POST" })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.already) { btn.disabled = false; return; }
      showToast(T("toast.reencode_started"), "success");
      var card = document.querySelector('.video-card[data-id="' + id + '"]');
      if (card) {
        // Add encoding status + progress bar
        var statusBlock = card.querySelector(".video-status-block");
        if (statusBlock) {
          statusBlock.innerHTML =
            '<div class="status-line encoding-dot" id="encode-status-' + id + '">\u25cf ' + T("video.status_waiting_full") + '</div>' +
            '<div class="progress"><div class="progress-bar flame-progress" id="encode-progress-' + id + '" style="width:0%"></div></div>';
        }
        // Add encoding overlay to poster
        var posterBox = document.getElementById("video-poster-" + id);
        if (posterBox && !posterBox.querySelector(".video-encoding-overlay")) {
          var overlay = document.createElement("div");
          overlay.className = "video-encoding-overlay";
          overlay.innerText = T("video.status_queued");
          posterBox.appendChild(overlay);
        }
        // Replace action buttons with Cancel
        var actions = card.querySelector(".video-actions");
        if (actions) {
          actions.innerHTML =
            '<button class="secondary" onclick="cancelEncode(this, ' + id + ')">' + T("button.cancel") + '</button>';
        }
      }
      watchProgress(id);
    });
}

function delVid(btn, id) {
  var isConfirming = btn.dataset.confirming === "1";

  if (!isConfirming) {
    var card = btn.closest(".video-card");
    var titleEl = card && card.querySelector("h3");
    var title = titleEl ? titleEl.textContent.trim() : "Video #" + id;
    btn.dataset.confirming = "1";
    btn.dataset.originalText = btn.innerText;
    btn.innerText = T("confirm.delete_video", { title: title.length > 30 ? title.substring(0, 30) + "\u2026" : title });
    btn.classList.add("confirming-delete");

    clearTimeout(btn._confirmTimer);
    btn._confirmTimer = setTimeout(function () {
      btn.dataset.confirming = "0";
      btn.innerText = btn.dataset.originalText || T("button.delete");
      btn.classList.remove("confirming-delete");
    }, 3500);
    return;
  }

  btn.disabled = true;
  clearTimeout(btn._confirmTimer);
  fetch("/delete/" + id, { method: "POST" })
    .then(function () {
      showToast(T("toast.video_deleted"), "success");
      var card = btn.closest(".video-card");
      if (card) {
        card.style.transition = "opacity .3s ease, transform .3s ease";
        card.style.opacity = "0";
        card.style.transform = "scale(.97)";
        setTimeout(function () { card.remove(); }, 300);
      }
    });
}

function openHlsHelp() {
  var backdrop = document.getElementById('hls-help-backdrop');
  var flame = document.getElementById('hls-help-flame');
  backdrop.hidden = false;
  flame.classList.remove('is-active');
  void flame.offsetWidth;
  flame.classList.add('is-active');
}

function closeHlsHelp() {
  var backdrop = document.getElementById('hls-help-backdrop');
  backdrop.classList.add('is-closing');
  setTimeout(function () {
    backdrop.hidden = true;
    backdrop.classList.remove('is-closing');
  }, 260);
}

function openUrlHelp() {
  var backdrop = document.getElementById('url-help-backdrop');
  var flame = document.getElementById('url-help-flame');
  backdrop.hidden = false;
  flame.classList.remove('is-active');
  void flame.offsetWidth;
  flame.classList.add('is-active');
}

function closeUrlHelp() {
  var backdrop = document.getElementById('url-help-backdrop');
  backdrop.classList.add('is-closing');
  setTimeout(function () {
    backdrop.hidden = true;
    backdrop.classList.remove('is-closing');
  }, 260);
}

function copyToClipboard(text, message) {
  navigator.clipboard.writeText(text).then(function () {
    showToast(message || T("toast.copied"), "info");
  });
}

function showToast(message, kind) {
  kind = kind || "info";
  var toast = document.getElementById("toast");
  toast.className = "toast";
  toast.classList.add("toast--" + kind);
  toast.innerText = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { toast.classList.remove("show"); }, 3000);
}

function loadPlayer(el) {
  var src = el.dataset.src;
  var poster = el.dataset.poster;
  var vidId = el.dataset.id;

  var wrapper = document.createElement("div");
  wrapper.className = "video-player-wrapper";

  var video = document.createElement("video");
  video.controls = true;
  video.autoplay = true;
  video.poster = poster;
  video.style.width = "100%";
  video.style.height = "100%";
  video.style.objectFit = "contain";

  var btn = document.createElement("button");
  btn.className = "poster-set-btn";
  btn.type = "button";
  btn.innerText = T("button.set_poster");
  btn.hidden = true;

  btn.addEventListener("click", function () {
    setPoster(vidId, video.currentTime, btn);
  });

  video.addEventListener("pause", function () {
    if (video.currentTime > 0 && !video.ended) btn.hidden = false;
  });
  video.addEventListener("play", function () { btn.hidden = true; });
  video.addEventListener("ended", function () { btn.hidden = true; });

  wrapper.appendChild(video);
  wrapper.appendChild(btn);
  el.replaceWith(wrapper);

  if (window.Hls && Hls.isSupported()) {
    var hls = new Hls();
    hls.loadSource(src);
    hls.attachMedia(video);
  } else {
    video.src = src;
  }
}

function setPoster(vidId, seconds, btn) {
  btn.disabled = true;
  btn.innerText = T("video.poster_creating");

  fetch("/video/" + vidId + "/poster", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ seconds: seconds }),
  })
    .then(function (r) {
      if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || T("toast.error")); });
      return r.json();
    })
    .then(function (data) {
      btn.innerText = "\u2713";
      btn.classList.add("is-success");
      showToast(T("toast.poster_set"), "success");
      if (data.poster_url) {
        var posterImg = document.querySelector("#video-poster-" + vidId + " img");
        if (posterImg) posterImg.src = data.poster_url;
      }
      setTimeout(function () {
        btn.hidden = true;
        btn.disabled = false;
        btn.innerText = T("button.set_poster");
        btn.classList.remove("is-success");
      }, 2000);
    })
    .catch(function (err) {
      btn.disabled = false;
      btn.innerText = T("button.set_poster");
      showToast(err.message || T("toast.error"), "error");
    });
}

function setupSearchAutoReset() {
  var form = document.querySelector(".video-search");
  var input = document.getElementById("video-search-input");
  if (!form || !input) return;

  var hadValue = input.value.trim().length > 0;
  input.addEventListener("input", function () {
    var hasValue = input.value.trim().length > 0;
    if (hadValue && !hasValue) {
      form.submit();
    }
    hadValue = hasValue;
  });
}

setupSearchAutoReset();

function startTitleEdit(id) {
  var row = document.getElementById("video-title-row-" + id);
  var form = document.getElementById("video-title-edit-" + id);
  var input = document.getElementById("video-title-input-" + id);
  if (!row || !form || !input) return;

  row.hidden = true;
  form.hidden = false;
  input.focus();
  input.select();
}

function cancelTitleEdit(id) {
  var row = document.getElementById("video-title-row-" + id);
  var form = document.getElementById("video-title-edit-" + id);
  if (!row || !form) return;
  row.hidden = false;
  form.hidden = true;
}

function saveTitleEdit(event, id) {
  event.preventDefault();
  var input = document.getElementById("video-title-input-" + id);
  var form = document.getElementById("video-title-edit-" + id);
  if (!input || !form) return;

  var title = input.value.trim();
  if (!title) {
    showToast(T("validation.title_required"));
    input.focus();
    return;
  }

  var buttons = Array.from(form.querySelectorAll("button"));
  buttons.forEach(function (b) { b.disabled = true; });

  fetch("/video/" + id + "/title", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title }),
  })
    .then(function (r) {
      if (!r.ok) {
        return r.json().then(function (data) {
          var msg = T("toast.error");
          if (data && data.detail) msg = data.detail;
          throw new Error(msg);
        });
      }
      return r.json();
    })
    .then(function () {
      // Update title in display
      var display = document.getElementById("video-title-display-" + id);
      if (display) display.textContent = title;
      // Switch back to display mode
      var row = document.getElementById("video-title-row-" + id);
      if (row) row.hidden = false;
      form.hidden = true;
      buttons.forEach(function (b) { b.disabled = false; });
    })
    .catch(function (err) {
      showToast(err.message || T("toast.error"));
      buttons.forEach(function (b) { b.disabled = false; });
    });
}

// Wire up page size custom selects
document.querySelectorAll(".pagesize-select").forEach(function (sel) {
  sel.addEventListener("change", function (e) {
    var val = e.detail.value;
    localStorage.setItem("eyestream-per-page", val);
    window.location.href = "/?page=1" + PAGE_DATA.pageSizeUrlSuffix + "&per_page=" + val;
  });
});

// Wire up filter category custom select
var filterSel = document.getElementById("cat-filter");
if (filterSel) {
  filterSel.addEventListener("change", function (e) {
    document.getElementById("cat-filter-value").value = e.detail.value;
    filterSel.closest("form").submit();
  });
}

// Wire up inline category custom selects
document.querySelectorAll(".custom-select--flame[data-vid]").forEach(function (sel) {
  sel.addEventListener("change", function (e) {
    var vid = sel.dataset.vid;
    var val = e.detail.value;
    sel.classList.add("is-saving");

    fetch("/video/" + vid + "/category", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category_id: val || null }),
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || T("toast.error")); });
        return r.json();
      })
      .then(function () {
        sel.classList.remove("is-saving");
        showToast(T("toast.category_changed"), "success");
      })
      .catch(function (err) {
        sel.classList.remove("is-saving");
        showToast(err.message || T("toast.error"), "error");
      });
  });
});

// Note contenteditable: clear highlights on focus, restore on blur
document.querySelectorAll(".video-note-input[contenteditable]").forEach(function (el) {
  el.addEventListener("focus", function () {
    var raw = el.innerText;
    el.dataset.raw = raw;
    el.textContent = raw;
  });
  el.addEventListener("blur", function () {
    el.dataset.raw = el.innerText;
  });
  el.addEventListener("keydown", function (e) {
    if (e.key === "Enter") e.preventDefault();
  });
  el.addEventListener("paste", function (e) {
    e.preventDefault();
    var text = (e.clipboardData || window.clipboardData).getData("text/plain");
    document.execCommand("insertText", false, text);
  });
});

function saveNote(btn, id) {
  var el = document.getElementById("video-note-input-" + id);
  if (!el) return;

  btn.disabled = true;
  var note = el.innerText || "";

  fetch("/video/" + id + "/note", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: note }),
  })
    .then(function (r) {
      if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || T("toast.error")); });
      return r.json();
    })
    .then(function (data) {
      if (data && typeof data.note === "string") {
        el.innerText = data.note;
        el.dataset.raw = data.note;
      }
      showToast(T("toast.note_saved"));
      btn.disabled = false;
    })
    .catch(function (err) {
      showToast(err.message || T("toast.error"));
      btn.disabled = false;
    });
}

// Start watching encoding progress for active videos
if (typeof PAGE_DATA !== "undefined" && PAGE_DATA.encodingIds) {
  PAGE_DATA.encodingIds.forEach(function (id) {
    watchProgress(id);
  });
}

// Double-click on title to edit
document.querySelectorAll(".video-title-row h3").forEach(function (h3) {
  h3.style.cursor = "pointer";
  h3.addEventListener("dblclick", function () {
    var row = h3.closest(".video-title-row");
    if (!row) return;
    var id = row.id.replace("video-title-row-", "");
    startTitleEdit(id);
  });
});

// Search suggestions
(function setupSearchSuggest() {
  var input = document.getElementById("video-search-input");
  var panel = document.getElementById("search-suggest");
  var form = input && input.closest("form");
  if (!input || !panel || !form) return;

  var timer = null;
  var activeIdx = -1;

  input.addEventListener("input", function () {
    clearTimeout(timer);
    var q = input.value.trim();
    if (q.length < 2) { panel.hidden = true; return; }
    timer = setTimeout(function () {
      fetch("/search/suggest?q=" + encodeURIComponent(q))
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data || !data.suggestions || !data.suggestions.length) { panel.hidden = true; return; }
          activeIdx = -1;
          panel.innerHTML = data.suggestions.map(function (s, i) {
            return '<div class="search-suggest-item" data-idx="' + i + '" data-type="' + esc(s.type) + '" data-value="' + esc(s.value) + '">' +
              '<span class="search-suggest-text">' + esc(s.label) + '</span>' +
              '<span class="search-suggest-type">' + esc(s.type === "bereich" ? T("label.category") : s.type) + '</span></div>';
          }).join("");
          panel.hidden = false;

          panel.querySelectorAll(".search-suggest-item").forEach(function (item) {
            item.addEventListener("mousedown", function (e) {
              e.preventDefault();
              selectSuggestion(item);
            });
          });
        });
    }, 200);
  });

  input.addEventListener("keydown", function (e) {
    if (panel.hidden) return;
    var items = panel.querySelectorAll(".search-suggest-item");
    if (e.key === "ArrowDown") { e.preventDefault(); activeIdx = Math.min(activeIdx + 1, items.length - 1); highlight(items); }
    else if (e.key === "ArrowUp") { e.preventDefault(); activeIdx = Math.max(activeIdx - 1, -1); highlight(items); }
    else if (e.key === "Enter" && activeIdx >= 0) { e.preventDefault(); selectSuggestion(items[activeIdx]); }
    else if (e.key === "Escape") { panel.hidden = true; }
  });

  input.addEventListener("blur", function () { setTimeout(function () { panel.hidden = true; }, 150); });

  function highlight(items) {
    items.forEach(function (it, i) { it.classList.toggle("is-active", i === activeIdx); });
  }

  function selectSuggestion(item) {
    if (item.dataset.type === "bereich") {
      document.getElementById("cat-filter-value").value = item.dataset.value;
      input.value = "";
      form.submit();
    } else {
      input.value = item.dataset.value;
      form.submit();
    }
    panel.hidden = true;
  }
})();

// Hover preview thumbnails
var previewCache = {};
var previewTimers = {};

document.querySelectorAll('.video-poster.is-playable').forEach(function (poster) {
  var vid = poster.dataset.id;
  if (!vid) return;
  poster.addEventListener('mouseenter', function () {
    var img = poster.querySelector('img');
    if (!img) return;
    if (!img.dataset.origSrc) img.dataset.origSrc = img.src;

    if (previewCache[vid]) {
      startPreviewRotation(poster, img, previewCache[vid]);
      return;
    }

    var base = (poster.dataset.src || '').replace(/\/master\.m3u8.*$/, '');
    if (!base) return;
    fetch(base + '/previews.json', { cache: 'force-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.length) return;
        previewCache[vid] = data.map(function (p) { return base + '/' + p.f; });
        startPreviewRotation(poster, img, previewCache[vid]);
      })
      .catch(function () {});
  });

  poster.addEventListener('mouseleave', function () {
    stopPreviewRotation(vid);
    var img = poster.querySelector('img');
    if (img && img.dataset.origSrc) img.src = img.dataset.origSrc;
  });
});

function startPreviewRotation(poster, img, urls) {
  var vid = poster.dataset.id;
  var idx = 0;
  stopPreviewRotation(vid);
  img.src = urls[0];
  previewTimers[vid] = setInterval(function () {
    idx = (idx + 1) % urls.length;
    img.src = urls[idx];
  }, 600);
}

function stopPreviewRotation(vid) {
  if (previewTimers[vid]) {
    clearInterval(previewTimers[vid]);
    delete previewTimers[vid];
  }
}

// Referer badges
(function loadReferers() {
  fetch("/referers", { cache: "no-store" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      if (!data) return;

      if (data.views) {
        Object.keys(data.views).forEach(function (vid) {
          var badge = document.getElementById("views-" + vid);
          if (!badge) return;
          var count = data.views[vid];
          if (count > 0) {
            badge.hidden = false;
            badge.innerText = count.toLocaleString(LANG === "de" ? "de-DE" : "en-US") + " " + T("stat.views");
          }
        });
      }

      if (!data.referers) return;
      var refs = data.referers;
      Object.keys(refs).forEach(function (vid) {
        var entry = refs[vid];
        if (!entry || !entry.domains || !entry.domains.length) return;
        var domains = entry.domains;
        var urls = entry.urls || [];
        var badge = document.getElementById("referer-badge-" + vid);
        if (!badge) return;
        badge.hidden = false;
        badge.innerText = domains.length + " Site" + (domains.length !== 1 ? "s" : "");

        var detailsId = "referer-details-" + vid;
        var tooltip = document.createElement("div");
        tooltip.className = "referer-tooltip";
        var domainUrlCounts = {};
        domains.forEach(function (d) { domainUrlCounts[d] = 0; });
        urls.forEach(function (u) {
          var uDomain = u.replace(/^https?:\/\//, '').split('/')[0].split(':')[0];
          domains.forEach(function (d) { if (uDomain === d || uDomain.endsWith('.' + d)) domainUrlCounts[d]++; });
        });

        var safeUrls = urls.filter(function (u) { return u.indexOf("https://") === 0; });
        tooltip.innerHTML =
          '<strong>' + T("referer.embedded_on") + '</strong> <span class="referer-period">' + T("referer.last_4_days") + '</span>' +
          '<div class="referer-domain-grid">' +
          domains.map(function (d) {
            return '<span class="referer-domain-count">' + (domainUrlCounts[d] || '') + '</span><span class="referer-domain">' + esc(d) + '</span>';
          }).join("") +
          '</div>' +
          (safeUrls.length ? '<button class="referer-details-btn" onclick="event.stopPropagation();var el=document.getElementById(\'' + detailsId + '\');el.hidden=!el.hidden;this.innerText=el.hidden?T(\'button.details\'):T(\'button.collapse\')">' + T("button.details") + '</button>' +
          '<div class="referer-urls" id="' + detailsId + '" hidden>' +
          safeUrls.map(function (u) { return '<a class="referer-url" href="' + esc(u) + '" target="_blank" rel="noopener noreferrer">' + esc(u.replace(/^https?:\/\//, '')) + '</a>'; }).join("") +
          '</div>' : '');
        badge.appendChild(tooltip);
      });
    })
    .catch(function () {});
})();
