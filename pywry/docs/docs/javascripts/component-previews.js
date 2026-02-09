/**
 * PyWry Component Preview Interactivity
 *
 * Pure client-side JS that makes the doc component previews interactive.
 * Handles: dropdowns, multiselect, tabs, number spinners, sliders,
 * range inputs, and secret input actions.
 *
 * All handlers are scoped to `.component-preview` containers so they
 * never collide with MkDocs Material or other page JS.
 *
 * Uses MkDocs Material's document$ observable so it works with
 * navigation.instant (XHR page loads).
 */
function initComponentPreviews() {
  // Bail early if no previews on this page
  var previews = document.querySelectorAll(".component-preview");
  if (!previews.length) return;

  // Guard against double-init: mark each preview once processed
  previews.forEach(function (p) {
    if (p.dataset.previewInit) return;
    p.dataset.previewInit = "1";
  });

  // ── Dropdowns (Select & MultiSelect) ─────────────────────────────
  // Toggle open/close when the trigger area is clicked
  document.querySelectorAll(".component-preview .pywry-dropdown-selected").forEach(function (trigger) {
    if (trigger.dataset.bound) return;
    trigger.dataset.bound = "1";
    trigger.addEventListener("click", function (e) {
      e.stopPropagation();
      var dropdown = trigger.closest(".pywry-dropdown");
      // Close any other open dropdowns first
      document.querySelectorAll(".component-preview .pywry-dropdown.pywry-open").forEach(function (d) {
        if (d !== dropdown) d.classList.remove("pywry-open");
      });
      dropdown.classList.toggle("pywry-open");
    });
  });

  // Single-select: click an option to select it
  document.querySelectorAll(".component-preview .pywry-dropdown:not(.pywry-multiselect) .pywry-dropdown-option").forEach(function (option) {
    if (option.dataset.bound) return;
    option.dataset.bound = "1";
    option.addEventListener("click", function (e) {
      e.stopPropagation();
      var dropdown = option.closest(".pywry-dropdown");
      var textEl = dropdown.querySelector(".pywry-dropdown-text");
      // Update selected class
      dropdown.querySelectorAll(".pywry-dropdown-option").forEach(function (o) {
        o.classList.remove("pywry-selected");
      });
      option.classList.add("pywry-selected");
      // Update display text
      if (textEl) textEl.textContent = option.textContent;
      // Close dropdown
      dropdown.classList.remove("pywry-open");
    });
  });

  // MultiSelect: toggle individual options
  document.querySelectorAll(".component-preview .pywry-multiselect .pywry-multiselect-option").forEach(function (option) {
    if (option.dataset.bound) return;
    option.dataset.bound = "1";
    option.addEventListener("click", function (e) {
      e.stopPropagation();
      var cb = option.querySelector("input[type=checkbox]");
      // The label click already toggles the checkbox, so just sync the class
      if (cb) {
        option.classList.toggle("pywry-selected", cb.checked);
      }
      updateMultiselectText(option.closest(".pywry-dropdown"));
    });
  });

  // MultiSelect: All / None buttons
  document.querySelectorAll(".component-preview .pywry-multiselect-action").forEach(function (btn) {
    if (btn.dataset.bound) return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var dropdown = btn.closest(".pywry-dropdown");
      var selectAll = btn.getAttribute("data-action") === "all";
      dropdown.querySelectorAll(".pywry-multiselect-option").forEach(function (opt) {
        var cb = opt.querySelector("input[type=checkbox]");
        if (cb) {
          cb.checked = selectAll;
          opt.classList.toggle("pywry-selected", selectAll);
        }
      });
      updateMultiselectText(dropdown);
    });
  });

  function updateMultiselectText(dropdown) {
    var textEl = dropdown.querySelector(".pywry-dropdown-text");
    if (!textEl) return;
    var selected = [];
    dropdown.querySelectorAll(".pywry-multiselect-option.pywry-selected .pywry-multiselect-label").forEach(function (lbl) {
      selected.push(lbl.textContent);
    });
    textEl.textContent = selected.length ? selected.join(", ") : "None selected";
  }

  // ── Searchable Select filtering ───────────────────────────────────
  document.querySelectorAll(".component-preview .pywry-dropdown.pywry-searchable .pywry-search-input").forEach(function (input) {
    if (input.dataset.bound) return;
    input.dataset.bound = "1";
    input.addEventListener("input", function () {
      var query = input.value.toLowerCase();
      var dropdown = input.closest(".pywry-dropdown");
      dropdown.querySelectorAll(".pywry-dropdown-option").forEach(function (opt) {
        var text = opt.textContent.toLowerCase();
        opt.style.display = text.indexOf(query) !== -1 ? "" : "none";
      });
    });
    // Prevent dropdown close when clicking in the search box
    input.addEventListener("click", function (e) {
      e.stopPropagation();
    });
  });

  // ── MultiSelect search filtering ─────────────────────────────────
  document.querySelectorAll(".component-preview .pywry-dropdown.pywry-multiselect .pywry-search-input").forEach(function (input) {
    if (input.dataset.bound) return;
    input.dataset.bound = "1";
    input.addEventListener("input", function () {
      var query = input.value.toLowerCase();
      var dropdown = input.closest(".pywry-dropdown");
      dropdown.querySelectorAll(".pywry-multiselect-option").forEach(function (opt) {
        var text = opt.textContent.toLowerCase();
        opt.style.display = text.indexOf(query) !== -1 ? "" : "none";
      });
    });
    // Prevent dropdown close when clicking in the search box
    input.addEventListener("click", function (e) {
      e.stopPropagation();
    });
  });

  // ── TabGroup ──────────────────────────────────────────────────────
  document.querySelectorAll(".component-preview .pywry-tab-group").forEach(function (group) {
    if (group.dataset.bound) return;
    group.dataset.bound = "1";
    group.querySelectorAll(".pywry-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        group.querySelectorAll(".pywry-tab").forEach(function (t) {
          t.classList.remove("pywry-tab-active");
        });
        tab.classList.add("pywry-tab-active");
      });
    });
  });

  // ── NumberInput Spinner ───────────────────────────────────────────
  document.querySelectorAll(".component-preview .pywry-number-spinner").forEach(function (spinner) {
    if (spinner.dataset.bound) return;
    spinner.dataset.bound = "1";
    var buttons = spinner.querySelectorAll("button");
    var input = spinner.closest(".pywry-number-wrapper").querySelector("input[type=number]");
    if (!input || buttons.length < 2) return;

    // First button = up (▲), second = down (▼)
    buttons[0].addEventListener("click", function () {
      input.stepUp();
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    buttons[1].addEventListener("click", function () {
      input.stepDown();
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  });

  // ── SliderInput ───────────────────────────────────────────────────
  document.querySelectorAll(".component-preview input.pywry-input-range").forEach(function (slider) {
    if (slider.dataset.bound) return;
    slider.dataset.bound = "1";
    var valueEl = slider.nextElementSibling;
    if (valueEl && valueEl.classList.contains("pywry-range-value")) {
      slider.addEventListener("input", function () {
        valueEl.textContent = slider.value;
      });
    }
  });

  // ── RangeInput (dual-handle) ──────────────────────────────────────
  document.querySelectorAll(".component-preview .pywry-range-group").forEach(function (group) {
    if (group.dataset.bound) return;
    group.dataset.bound = "1";
    var startInput = group.querySelector('input[data-range="start"]');
    var endInput = group.querySelector('input[data-range="end"]');
    var startLabel = group.querySelector(".pywry-range-start-value");
    var endLabel = group.querySelector(".pywry-range-end-value");
    var fill = group.querySelector(".pywry-range-track-fill");
    if (!startInput || !endInput) return;

    function updateRange() {
      var min = parseFloat(startInput.min);
      var max = parseFloat(startInput.max);
      var startVal = parseFloat(startInput.value);
      var endVal = parseFloat(endInput.value);

      // Prevent handles from crossing
      if (startVal > endVal) {
        startInput.value = endVal;
        startVal = endVal;
      }

      // Detect currency prefix from existing label text
      var prefix = "";
      if (startLabel) {
        var m = startLabel.textContent.match(/^([^0-9]*)/);
        if (m) prefix = m[1];
      }
      if (startLabel) startLabel.textContent = prefix + startVal;
      if (endLabel) endLabel.textContent = prefix + endVal;

      if (fill) {
        var leftPct = ((startVal - min) / (max - min)) * 100;
        var widthPct = ((endVal - startVal) / (max - min)) * 100;
        fill.style.left = leftPct + "%";
        fill.style.width = widthPct + "%";
      }
    }

    startInput.addEventListener("input", updateRange);
    endInput.addEventListener("input", updateRange);
  });

  // ── SecretInput ───────────────────────────────────────────────────
  document.querySelectorAll(".component-preview .pywry-secret-wrapper").forEach(function (wrapper) {
    if (wrapper.dataset.bound) return;
    wrapper.dataset.bound = "1";
    var input = wrapper.querySelector("input");
    var editBtn = wrapper.querySelector(".pywry-secret-edit");
    var copyBtn = wrapper.querySelector(".pywry-secret-copy");
    var toggleBtn = wrapper.querySelector(".pywry-secret-toggle");
    if (!input) return;

    // Edit: toggle readonly and focus
    if (editBtn) {
      editBtn.addEventListener("click", function () {
        if (input.readOnly) {
          input.readOnly = false;
          input.focus();
          editBtn.classList.add("pywry-active");
        } else {
          input.readOnly = true;
          editBtn.classList.remove("pywry-active");
        }
      });
    }

    // Copy to clipboard
    if (copyBtn) {
      copyBtn.addEventListener("click", function () {
        navigator.clipboard.writeText(input.value).then(function () {
          copyBtn.classList.add("pywry-active");
          setTimeout(function () {
            copyBtn.classList.remove("pywry-active");
          }, 1200);
        });
      });
    }

    // Toggle password visibility
    if (toggleBtn) {
      toggleBtn.addEventListener("click", function () {
        input.type = input.type === "password" ? "text" : "password";
        toggleBtn.classList.toggle("pywry-active", input.type === "text");
      });
    }
  });
}

// ── Close dropdowns on outside click (global, only bound once) ────
(function () {
  var closeBound = false;
  function ensureCloseHandler() {
    if (closeBound) return;
    closeBound = true;
    document.addEventListener("click", function () {
      document.querySelectorAll(".component-preview .pywry-dropdown.pywry-open").forEach(function (d) {
        d.classList.remove("pywry-open");
      });
    });
  }

  // MkDocs Material with navigation.instant exposes document$
  // which fires on every page load (initial + XHR navigations).
  if (typeof document$ !== "undefined") {
    document$.subscribe(function () {
      ensureCloseHandler();
      initComponentPreviews();
    });
  } else {
    // Fallback: standard page load
    document.addEventListener("DOMContentLoaded", function () {
      ensureCloseHandler();
      initComponentPreviews();
    });
  }
})();
