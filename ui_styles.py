APP_CSS = """
:root {
  --studio-bg: #f8fafc;
  --panel: #ffffff;
  --panel-soft: #f1f3f5;
  --line: #e4e7eb;
  --line-strong: #cbd5e1;
  --muted: #64748b;
  --ink: #0f172a;
  --ink-soft: #1e293b;
  --primary: #1e3a5f;
  --secondary: #2563eb;
  --accent: #059669;
  --accent-hover: #047857;
  --accent-soft: #e7f7f1;
  --gold: #9a6a1d;
  --danger: #dc2626;
  --ring: #1e3a5f;
  --shadow-sm: none;
  --shadow-md: none;
  --radius: 8px;
}

body,
.gradio-container {
  background: var(--studio-bg) !important;
  color: var(--ink) !important;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

.gradio-container {
  padding: 18px !important;
  --button-primary-background-fill: var(--primary);
  --button-primary-background-fill-hover: #172f4d;
  --button-primary-text-color: #ffffff;
  --button-secondary-background-fill: #ffffff;
  --button-secondary-background-fill-hover: var(--panel-soft);
  --button-secondary-border-color: var(--line-strong);
  --button-secondary-text-color: var(--ink);
  --checkbox-label-background-fill-selected: var(--accent-soft);
  --checkbox-label-border-color-selected: #b7e4d4;
  --checkbox-label-text-color-selected: var(--accent-hover);
  --slider-color: var(--secondary);
  --input-border-color-focus: var(--ring);
}

.studio-root {
  max-width: 1680px !important;
  margin: 0 auto !important;
}

.studio-shell {
  gap: 16px !important;
  align-items: stretch !important;
}

.sidebar,
.main-pane {
  background: var(--panel) !important;
  border: 1px solid var(--line) !important;
  border-radius: var(--radius) !important;
  box-shadow: none !important;
}

.sidebar {
  padding: 18px 14px !important;
  min-height: calc(100vh - 36px);
  position: sticky;
  top: 18px;
  align-self: flex-start;
  flex: 0 0 240px !important;
  max-width: 260px !important;
}

.main-pane {
  padding: 24px !important;
  min-height: calc(100vh - 36px);
  flex: 1 1 0 !important;
  min-width: 0 !important;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 26px;
}

.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: var(--primary);
  color: white;
  display: grid;
  place-items: center;
  font-weight: 850;
  letter-spacing: 0;
  box-shadow: none;
}

.brand-title {
  font-size: 20px;
  line-height: 1.04;
  font-weight: 780;
  letter-spacing: 0;
}

.brand-subtitle {
  color: var(--muted);
  font-size: 12px;
  margin-top: 5px;
}

.nav-radio {
  border: 0 !important;
  padding: 0 !important;
  background: transparent !important;
}

.nav-radio > label,
.nav-radio .block-label,
.small-actions > label,
.small-actions .block-label {
  display: none !important;
}

.nav-radio > span,
.small-actions > span {
  display: none !important;
}

.nav-radio .wrap {
  display: grid !important;
  gap: 6px !important;
  background: transparent !important;
}

.nav-radio label {
  width: 100% !important;
  min-height: 46px !important;
  border: 1px solid transparent !important;
  border-radius: var(--radius) !important;
  padding: 0 12px !important;
  display: flex !important;
  align-items: center !important;
  color: var(--ink-soft) !important;
  font-size: 15px !important;
  cursor: pointer;
  transition: background 180ms ease, border-color 180ms ease, color 180ms ease;
}

.nav-radio label:hover {
  background: var(--panel-soft) !important;
  border-color: var(--line) !important;
}

.nav-radio label:has(input:checked) {
  background: var(--accent-soft) !important;
  border-color: #b7e4d4 !important;
  color: var(--accent-hover) !important;
  font-weight: 720 !important;
}

.nav-radio input[type="radio"] {
  margin-right: 12px !important;
  accent-color: var(--accent) !important;
}

.page-block {
  gap: 16px;
}

.page-title {
  border-bottom: 1px solid var(--line);
  padding-bottom: 14px;
  margin-bottom: 2px;
}

.page-title span {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border-radius: 999px;
  padding: 0 10px;
  background: var(--accent-soft);
  color: var(--accent-hover);
  font-size: 12px;
  font-weight: 760;
}

.page-title h1 {
  font-size: 34px;
  margin: 8px 0 0;
  font-weight: 760;
  letter-spacing: 0;
}

.subtle {
  color: var(--muted);
  font-size: 14px;
}

.landing-page {
  gap: 18px !important;
}

.landing-hero {
  position: relative;
  min-height: 430px;
  overflow: hidden;
  border-radius: var(--radius);
  border: 1px solid #d6e3ea;
  background: #0f1f2e;
  isolation: isolate;
}

.landing-scene {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(140deg, rgba(15, 31, 46, 0.94) 0%, rgba(22, 78, 99, 0.76) 52%, rgba(246, 248, 244, 0.18) 100%),
    linear-gradient(0deg, rgba(5, 150, 105, 0.22), rgba(37, 99, 235, 0.16));
}

.signal-grid {
  position: absolute;
  inset: 0;
  opacity: 0.26;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.12) 1px, transparent 1px);
  background-size: 44px 44px;
}

.signal-panel {
  position: absolute;
  right: -14px;
  bottom: 36px;
  width: min(54%, 520px);
  min-width: 320px;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.26);
  border-radius: var(--radius);
  background: rgba(248, 250, 252, 0.14);
  box-shadow: 0 24px 80px rgba(2, 6, 23, 0.28);
  opacity: 0.48;
}

.signal-toolbar {
  display: flex;
  gap: 7px;
  margin-bottom: 16px;
}

.signal-toolbar span {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
}

.waveform {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  align-items: center;
  gap: 8px;
  height: 82px;
}

.waveform i {
  display: block;
  height: var(--h);
  min-height: 18px;
  border-radius: 6px;
  background: linear-gradient(180deg, #f8fafc 0%, #a7f3d0 100%);
  opacity: 0.92;
  animation: voice-pulse 2.8s ease-in-out infinite;
}

.waveform i:nth-child(2n) {
  animation-delay: 180ms;
}

.waveform i:nth-child(3n) {
  animation-delay: 340ms;
}

.timeline-line {
  height: 1px;
  margin: 14px 0;
  background: rgba(255, 255, 255, 0.26);
}

.voice-chip {
  position: absolute;
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  background: rgba(255, 255, 255, 0.16);
  color: #f8fafc;
  font-size: 13px;
  font-weight: 760;
}

.chip-kokoro {
  top: 34px;
  right: 42px;
}

.chip-vieneu {
  top: 82px;
  right: 122px;
}

.voice-meter {
  position: absolute;
  right: 72px;
  top: 150px;
  display: flex;
  align-items: end;
  gap: 6px;
  height: 54px;
}

.voice-meter span {
  width: 9px;
  border-radius: 999px;
  background: #fbbf24;
}

.voice-meter span:nth-child(1) { height: 22px; }
.voice-meter span:nth-child(2) { height: 46px; }
.voice-meter span:nth-child(3) { height: 34px; }
.voice-meter span:nth-child(4) { height: 54px; }
.voice-meter span:nth-child(5) { height: 28px; }

.landing-hero::after {
  content: "";
  position: absolute;
  inset: auto 0 0 0;
  height: 45%;
  background: linear-gradient(180deg, rgba(15, 31, 46, 0), rgba(15, 31, 46, 0.82));
  z-index: 0;
}

.landing-hero-copy {
  position: relative;
  z-index: 1;
  max-width: 700px;
  padding: 52px;
  color: #ffffff;
  text-shadow: 0 2px 16px rgba(2, 6, 23, 0.32);
}

.landing-kicker,
.landing-section-heading span,
.workflow-copy span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  border-radius: 999px;
  padding: 0 11px;
  font-size: 12px;
  font-weight: 780;
  background: rgba(167, 243, 208, 0.16);
  color: #bbf7d0;
}

.landing-hero h1 {
  max-width: 620px;
  margin: 18px 0 14px;
  color: #ffffff !important;
  font-size: 64px;
  line-height: 0.98;
  font-weight: 850;
  letter-spacing: 0;
}

.landing-hero p {
  max-width: 610px;
  margin: 0;
  color: #eef8ff !important;
  font-size: 18px;
  line-height: 1.65;
}

.landing-proof {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 24px;
}

.landing-proof span {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0 13px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.22);
  color: #f8fafc;
  font-size: 13px;
  font-weight: 720;
}

.landing-actions {
  gap: 10px !important;
}

.landing-actions > .form {
  min-width: 210px !important;
}

.landing-section,
.landing-workflow {
  margin-top: 8px;
}

.landing-section-heading,
.workflow-copy {
  max-width: 760px;
  margin-bottom: 16px;
}

.landing-section-heading span,
.workflow-copy span {
  background: var(--accent-soft);
  color: var(--accent-hover);
}

.landing-section-heading h2,
.workflow-copy h2 {
  margin: 10px 0 0;
  color: var(--ink);
  font-size: 30px;
  line-height: 1.18;
  font-weight: 800;
  letter-spacing: 0;
}

.landing-feature-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.landing-card,
.workflow-step {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: #ffffff;
}

.landing-card {
  padding: 18px;
}

.landing-card-label {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: #e9f6f2;
  color: var(--accent-hover);
  font-size: 13px;
  font-weight: 820;
}

.landing-card h3 {
  margin: 16px 0 8px;
  font-size: 18px;
  line-height: 1.25;
  color: var(--ink);
  letter-spacing: 0;
}

.landing-card p {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
}

.landing-workflow {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(0, 1.2fr);
  gap: 14px;
  align-items: stretch;
  border: 1px solid #dce8ef;
  border-radius: var(--radius);
  background: #f6faf9;
  padding: 18px;
}

.workflow-copy {
  margin-bottom: 0;
}

.workflow-steps {
  display: grid;
  gap: 8px;
}

.workflow-step {
  display: grid;
  grid-template-columns: 42px 1fr;
  gap: 10px;
  align-items: center;
  min-height: 64px;
  padding: 12px;
}

.workflow-step strong {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: var(--primary);
  color: #ffffff;
  font-size: 14px;
}

.workflow-step span {
  color: var(--ink-soft);
  line-height: 1.45;
}

.landing-system-card {
  margin-top: 0 !important;
}

@keyframes voice-pulse {
  0%,
  100% {
    transform: scaleY(0.78);
    opacity: 0.72;
  }
  50% {
    transform: scaleY(1);
    opacity: 1;
  }
}

.section-card {
  border: 1px solid var(--line) !important;
  border-radius: var(--radius) !important;
  background: var(--panel) !important;
  padding: 18px !important;
  margin-bottom: 14px !important;
  box-shadow: none !important;
}

.section-card:hover {
  border-color: var(--line-strong) !important;
}

.section-card .block:has(.section-title),
.right-section .block:has(.section-title),
.page-block .block:has(.page-title),
.page-block .block:has(.create-studio-hero),
.page-block .block:has(.landing-hero),
.page-block .block:has(.landing-section),
.page-block .block:has(.landing-workflow),
.section-card .block:has(.tts-editor-head),
.section-card .block:has(.tts-result-head),
.section-card .block:has(.clone-studio-head),
.section-card .block:has(.clone-result-head) {
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  padding: 0 !important;
  min-height: auto !important;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 9px;
  background: transparent !important;
  font-size: 18px;
  font-weight: 780;
  margin: 0 0 12px;
  color: var(--ink);
}

.section-title::before {
  content: "";
  width: 4px;
  height: 18px;
  border-radius: 999px;
  background: var(--accent);
  flex: 0 0 auto;
}

.create-studio-page {
  gap: 12px !important;
}

.create-studio-hero {
  border: 1px solid #dfe5ee;
  border-radius: var(--radius);
  background:
    linear-gradient(135deg, rgba(17, 24, 39, 0.05), rgba(5, 150, 105, 0.08)),
    #ffffff;
  padding: 14px 16px;
}

.create-workbench {
  align-items: flex-start !important;
  gap: 14px !important;
  flex-wrap: wrap !important;
}

.create-main-panel,
.create-control-panel {
  gap: 12px !important;
}

.create-main-panel {
  flex: 1 1 100% !important;
  max-width: 100% !important;
  min-width: 0 !important;
}

.create-control-panel {
  align-self: flex-start !important;
  display: grid !important;
  flex: 1 1 100% !important;
  grid-template-columns: minmax(210px, 0.95fr) minmax(340px, 1.55fr) minmax(210px, 0.85fr);
  gap: 10px !important;
  max-width: 100% !important;
  order: -1;
  position: static;
  width: 100% !important;
}

.create-mode-switch {
  border: 0 !important;
  background: transparent !important;
  padding: 0 !important;
  margin: -2px 0 2px !important;
}

.create-mode-switch > label,
.create-mode-switch > span,
.create-mode-switch .block-label {
  display: none !important;
}

.create-mode-switch .wrap {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 6px !important;
  padding: 5px !important;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: #f8fafc;
}

.create-mode-switch label {
  min-height: 42px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  border: 1px solid transparent !important;
  border-radius: 7px !important;
  padding: 0 14px !important;
  color: var(--muted) !important;
  font-size: 14px !important;
  font-weight: 760 !important;
  cursor: pointer !important;
  transition: background 180ms ease, border-color 180ms ease, color 180ms ease !important;
}

.create-mode-switch label:hover {
  background: #ffffff !important;
  border-color: var(--line) !important;
  color: var(--ink-soft) !important;
}

.create-mode-switch label:has(input:checked) {
  background: #111827 !important;
  border-color: #111827 !important;
  color: #ffffff !important;
}

.create-mode-switch input[type="radio"] {
  display: none !important;
}

.create-studio-title {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  margin-top: 0;
}

.create-kicker,
.tts-step-label {
  color: var(--accent-hover);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.create-studio-title h1 {
  margin: 5px 0 0;
  color: #111827;
  font-size: 30px;
  line-height: 1.08;
  font-weight: 830;
  letter-spacing: 0;
}

.create-credit-pill {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0 13px;
  background: #ecfdf5;
  border: 1px solid #bbf7d0;
  color: #047857;
  font-size: 13px;
  font-weight: 780;
  white-space: nowrap;
}

.eleven-editor-card {
  padding: 0 !important;
  overflow: hidden;
  border-color: #d7dee8 !important;
  background: #ffffff !important;
}

.tts-editor-head,
.tts-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--line);
  background: #ffffff;
}

.tts-editor-head h2,
.tts-result-head h2 {
  margin: 4px 0 0;
  color: #111827;
  font-size: 22px;
  line-height: 1.1;
  font-weight: 820;
  letter-spacing: 0;
}

.tts-editor-badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
}

.tts-editor-badges span {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0 11px;
  background: #f8fafc;
  border: 1px solid var(--line);
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 720;
}

.direct-card {
  border-color: var(--line-strong) !important;
  box-shadow: none !important;
}

.direct-card textarea {
  min-height: 300px !important;
  font-size: 17px !important;
  line-height: 1.68 !important;
  border: 1px solid var(--line) !important;
  background: #ffffff !important;
}

.eleven-editor-card .tts-script-input,
.eleven-editor-card .tts-script-input > .form,
.eleven-editor-card .tts-script-input .block {
  border: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}

.eleven-editor-card textarea {
  height: 185px !important;
  min-height: 185px !important;
  border: 0 !important;
  border-radius: 0 !important;
  padding: 18px 18px 15px !important;
  background:
    linear-gradient(#ffffff, #ffffff) padding-box,
    linear-gradient(90deg, rgba(5, 150, 105, 0.08), rgba(37, 99, 235, 0.07)) border-box !important;
  color: #111827 !important;
  font-size: 17px !important;
  line-height: 1.62 !important;
  resize: vertical !important;
}

.eleven-editor-card textarea::placeholder {
  color: #9aa4b2 !important;
}

.direct-card textarea:focus,
.direct-card input:focus,
.direct-card select:focus,
button:focus-visible,
textarea:focus,
input:focus,
select:focus {
  border-color: var(--ring) !important;
  box-shadow: 0 0 0 3px rgba(30, 58, 95, 0.16) !important;
  outline: none !important;
}

.eleven-options {
  margin: 0 !important;
  border-width: 1px 0 0 0 !important;
  border-radius: 0 !important;
  background: #f8fafc !important;
  padding: 10px 12px !important;
}

.tts-char-meter {
  margin: 0 !important;
  padding: 12px 16px 0 !important;
  border-top: 1px solid var(--line);
  background: #ffffff;
}

.tts-generate-bar {
  margin: 0 !important;
  padding: 10px 16px 14px !important;
  background: #ffffff;
  align-items: stretch !important;
  gap: 10px !important;
  flex-wrap: wrap !important;
}

.tts-generate-bar > .form,
.tts-generate-bar > .block {
  flex: 1 1 120px !important;
  width: auto !important;
  min-width: 112px !important;
  max-width: none !important;
}

.tts-generate-bar button {
  width: 100% !important;
  min-width: 0 !important;
  min-height: 42px !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding-left: 14px !important;
  padding-right: 14px !important;
  white-space: nowrap !important;
}

.tts-char-meter p {
  margin: 0 !important;
  color: #667085 !important;
  font-size: 13px !important;
}

.result-card {
  background: var(--panel-soft) !important;
}

.eleven-result-card {
  padding: 0 !important;
  overflow: hidden;
  background: #fbfcfe !important;
  border-color: #d7dee8 !important;
}

.eleven-result-card audio {
  padding: 16px 18px 4px;
}

.eleven-result-card textarea {
  min-height: 76px !important;
  border: 0 !important;
  border-top: 1px solid var(--line) !important;
  border-radius: 0 !important;
  background: #ffffff !important;
}

.create-mode-panel {
  gap: 14px !important;
}

.clone-studio-card,
.clone-preview-card {
  padding: 0 !important;
  overflow: hidden;
  border-color: #d7dee8 !important;
  background: #ffffff !important;
}

.clone-studio-head,
.clone-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--line);
  background: #ffffff;
}

.clone-studio-head h2,
.clone-result-head h2 {
  margin: 4px 0 0;
  color: #111827;
  font-size: 22px;
  line-height: 1.1;
  font-weight: 820;
  letter-spacing: 0;
}

.clone-source-row,
.clone-settings-row {
  margin: 0 !important;
  padding: 14px 16px 0 !important;
  gap: 10px !important;
  align-items: end !important;
}

.clone-source-row > .form,
.clone-source-row > .block,
.clone-settings-row > .form,
.clone-settings-row > .block {
  flex: 1 1 150px !important;
  min-width: 140px !important;
}

.clone-source-row button {
  width: 100% !important;
  min-height: 42px !important;
}

.clone-studio-card > .styler,
.clone-preview-card > .styler {
  gap: 0 !important;
}

.clone-studio-card .block,
.clone-preview-card .block {
  box-shadow: none !important;
}

.clone-studio-card > .styler > .form,
.clone-studio-card > .styler > .block:not(:has(.clone-studio-head)),
.clone-studio-card > .styler > .wrap {
  margin-left: 16px !important;
  margin-right: 16px !important;
}

.clone-studio-card textarea {
  min-height: 116px !important;
  line-height: 1.58 !important;
}

.clone-studio-card audio {
  padding: 0 !important;
}

.clone-action-row {
  margin: 0 !important;
  padding: 14px 16px 16px !important;
  border-top: 1px solid var(--line);
  background: #ffffff;
  gap: 10px !important;
  align-items: stretch !important;
  flex-wrap: wrap !important;
}

.clone-action-row > .form,
.clone-action-row > .block {
  flex: 1 1 150px !important;
  min-width: 140px !important;
}

.clone-action-row button {
  width: 100% !important;
  min-height: 46px !important;
}

.clone-preview-card audio {
  padding: 16px 18px 4px;
}

.clone-preview-card textarea {
  min-height: 112px !important;
  border: 0 !important;
  border-top: 1px solid var(--line) !important;
  border-radius: 0 !important;
  background: #ffffff !important;
}

.tts-wave-mini {
  display: flex;
  align-items: end;
  gap: 4px;
  height: 34px;
}

.tts-wave-mini span {
  width: 5px;
  border-radius: 999px;
  background: #111827;
  opacity: 0.78;
}

.tts-wave-mini span:nth-child(1) { height: 13px; }
.tts-wave-mini span:nth-child(2) { height: 24px; }
.tts-wave-mini span:nth-child(3) { height: 17px; }
.tts-wave-mini span:nth-child(4) { height: 30px; background: var(--accent); }
.tts-wave-mini span:nth-child(5) { height: 20px; }
.tts-wave-mini span:nth-child(6) { height: 26px; }

.result-card audio {
  width: 100%;
}

.right-section {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 14px !important;
  margin-bottom: 12px;
  background: #ffffff;
}

.right-section > .styler,
.right-section .styler {
  background: transparent !important;
}

.right-section:last-child {
  border-bottom: 1px solid var(--line);
  margin-bottom: 0;
}

.right-section .section-title {
  margin-bottom: 10px;
  font-size: 16px;
}

.right-section .subtle {
  margin-bottom: 8px;
}

.right-section .form,
.right-section .block {
  box-shadow: none !important;
}

.right-section label span {
  font-size: 13px !important;
}

.create-control-panel .right-section {
  padding: 10px !important;
  height: auto;
  margin-bottom: 0;
  background: #fbfcfe;
}

.create-control-panel .right-section:last-child {
  margin-bottom: 0;
}

.create-control-panel .section-title {
  font-size: 15px;
  margin-bottom: 7px;
}

.create-control-panel .subtle {
  font-size: 12px;
  margin-bottom: 6px;
}

.create-control-panel .form,
.create-control-panel .block {
  min-height: auto !important;
}

.create-control-panel .block.padded,
.create-control-panel .padded {
  padding: 8px 10px !important;
}

.create-control-panel .right-section .block:has(.section-title) {
  padding: 4px 6px !important;
}

.create-control-panel label span {
  font-size: 12px !important;
}

.create-control-panel button {
  min-height: 40px !important;
}

.create-control-panel .small-actions .wrap {
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 4px !important;
}

.create-control-panel .small-actions label {
  min-height: 30px !important;
  padding: 0 4px !important;
  font-size: 11px !important;
  line-height: 1.08 !important;
}

.create-control-panel .create-adjust-section .block:has(input[type="range"]) {
  padding-top: 4px !important;
  padding-bottom: 4px !important;
}

.create-control-panel .create-adjust-section .form {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 5px 6px !important;
}

.create-control-panel .create-adjust-section .form > .block,
.create-control-panel .create-adjust-section .form > fieldset {
  margin: 0 !important;
  padding: 6px 8px !important;
  width: 100% !important;
}

.create-control-panel .create-adjust-section .form > .small-actions,
.create-control-panel .create-adjust-section .form > fieldset:has(input[value="GPU"]) {
  grid-column: span 1;
}

.create-control-panel .create-adjust-section .form > fieldset:not(.small-actions) .wrap {
  display: grid !important;
  gap: 4px !important;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.create-control-panel .create-adjust-section .form > fieldset:not(.small-actions) label {
  min-height: 30px !important;
  padding: 0 5px !important;
}

.create-status-section .styler {
  display: flex !important;
  flex-direction: column;
  gap: 8px !important;
}

.create-status-section .styler > .block,
.create-status-section .styler > .form,
.create-status-section .styler > .row {
  margin: 0 !important;
  width: 100% !important;
}

.create-status-section .gpu-badge {
  padding: 8px 10px;
  font-size: 15px;
  line-height: 1.15;
}

.create-status-section textarea {
  height: 48px !important;
  min-height: 48px !important;
}

.create-status-section .compact-actions {
  align-content: stretch !important;
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px !important;
  margin: 0 !important;
}

.create-status-section .compact-actions button {
  min-height: 38px !important;
}

.tts-mode-panel:not([style*="display: none"]),
.clone-mode-panel:not([style*="display: none"]) {
  display: grid !important;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.95fr);
  gap: 12px !important;
  align-items: start !important;
}

.small-actions .wrap {
  gap: 8px;
}

.inline-options {
  align-items: stretch !important;
  gap: 8px !important;
  border: 1px solid var(--line) !important;
  border-radius: var(--radius) !important;
  background: #fbfdff !important;
  padding: 8px !important;
}

.inline-options .wrap,
.small-actions .wrap {
  gap: 8px !important;
}

.inline-options label,
.small-actions label {
  min-height: 40px !important;
  border-radius: 7px !important;
  border: 1px solid var(--line) !important;
  background: #ffffff !important;
  color: var(--ink-soft) !important;
  cursor: pointer !important;
  transition: background 180ms ease, border-color 180ms ease, color 180ms ease !important;
}

.small-actions .wrap {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
}

.small-actions label {
  justify-content: center !important;
  padding: 0 9px !important;
  text-align: center !important;
}

.inline-options label:has(input:checked),
.small-actions label:has(input:checked) {
  background: var(--accent-soft) !important;
  border-color: #b7e4d4 !important;
  color: var(--accent-hover) !important;
  font-weight: 700 !important;
}

.action-row {
  gap: 10px !important;
  align-items: stretch !important;
}

.compact-actions {
  margin-bottom: 12px !important;
}

.primary-dark button,
button.primary-dark,
.gradio-container button.primary {
  background: var(--primary) !important;
  color: white !important;
  border-color: var(--primary) !important;
  box-shadow: none !important;
}

.primary-dark button:hover,
button.primary-dark:hover,
.gradio-container button.primary:hover {
  background: #172f4d !important;
  border-color: #172f4d !important;
}

.primary-dark button:active,
.ghost-button button:active,
.danger-link button:active,
button.primary-dark:active,
button.ghost-button:active,
button.danger-link:active {
  transform: scale(0.99);
}

.big-action button,
button.big-action {
  min-height: 50px !important;
  font-weight: 780 !important;
  font-size: 16px !important;
}

.ghost-button button,
button.ghost-button,
.gradio-container button.secondary {
  background: #ffffff !important;
  border: 1px solid var(--line-strong) !important;
  color: var(--ink) !important;
  cursor: pointer !important;
  box-shadow: none !important;
}

.ghost-button button:hover,
button.ghost-button:hover,
.gradio-container button.secondary:hover {
  background: var(--panel-soft) !important;
  border-color: var(--primary) !important;
  color: var(--primary) !important;
}

.secondary-action button,
button.secondary-action {
  font-weight: 690 !important;
}

.danger-link button,
button.danger-link {
  color: var(--danger) !important;
  background: #ffffff !important;
  border: 1px solid #f0d1ce !important;
  cursor: pointer !important;
  box-shadow: none !important;
}

.danger-link button:hover,
button.danger-link:hover {
  background: #fff8f7 !important;
  border-color: var(--danger) !important;
}

.gpu-badge {
  background: var(--primary);
  color: white;
  border-radius: var(--radius);
  padding: 14px 18px;
  text-align: center;
  font-size: 26px;
  font-weight: 850;
  box-shadow: none;
}

.compact-checks .wrap {
  gap: 12px;
}

textarea,
input,
select {
  border-radius: var(--radius) !important;
}

input[type="radio"],
input[type="checkbox"] {
  accent-color: var(--accent) !important;
}

input[type="range"] {
  accent-color: var(--secondary) !important;
}

button {
  border-radius: var(--radius) !important;
  cursor: pointer !important;
  min-height: 44px !important;
  font-weight: 680 !important;
  letter-spacing: 0 !important;
  transition: background 180ms ease, border-color 180ms ease, color 180ms ease, transform 120ms ease !important;
}

button:disabled {
  cursor: not-allowed !important;
  opacity: 0.52 !important;
  transform: none !important;
}

button.reset-button,
button[data-testid="reset-button"] {
  width: 28px !important;
  height: 22px !important;
  min-height: 22px !important;
  margin: 0 !important;
  padding: 0 !important;
  display: inline-grid !important;
  place-items: center !important;
  border-radius: 0 var(--radius) var(--radius) 0 !important;
  line-height: 1 !important;
  font-size: 14px !important;
  font-weight: 700 !important;
  transform: none !important;
}

.task-table {
  font-size: 13px;
}

table {
  border-radius: var(--radius) !important;
  overflow: hidden;
}

.voice-library-table {
  min-height: 360px !important;
}

.voice-library-table table {
  border: 1px solid var(--line) !important;
}

.voice-library-table th {
  background: #f8fafc !important;
  color: var(--ink) !important;
  font-weight: 760 !important;
}

.voice-library-table td {
  color: var(--ink-soft) !important;
}

.model-manager-card {
  border-color: #c7d7ee !important;
}

.model-manager-row {
  align-items: end !important;
  gap: 12px !important;
}

.model-manager-card textarea {
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace !important;
  font-size: 12px !important;
  line-height: 1.55 !important;
}

.google-tts-page {
  gap: 14px !important;
}

.google-tts-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid #d6e3ea;
  border-radius: var(--radius);
  background:
    linear-gradient(135deg, rgba(13, 148, 136, 0.12), rgba(30, 58, 95, 0.08)),
    #ffffff;
  padding: 22px 24px;
}

.google-kicker {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  border-radius: 999px;
  padding: 0 11px;
  background: var(--accent-soft);
  color: var(--accent-hover);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.google-tts-hero h1 {
  margin: 10px 0 8px;
  color: var(--ink);
  font-size: 36px;
  line-height: 1.04;
  font-weight: 850;
  letter-spacing: 0;
}

.google-tts-hero p {
  max-width: 760px;
  margin: 0;
  color: var(--muted);
  font-size: 15px;
  line-height: 1.6;
}

.google-tts-meter {
  flex: 0 0 auto;
  width: 118px;
  height: 86px;
  display: flex;
  align-items: end;
  justify-content: center;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: #fbfcfe;
}

.google-tts-meter span {
  width: 10px;
  border-radius: 999px;
  background: var(--accent);
  opacity: 0.82;
  animation: voice-pulse 2.6s ease-in-out infinite;
}

.google-tts-meter span:nth-child(1) { height: 24px; }
.google-tts-meter span:nth-child(2) { height: 48px; animation-delay: 120ms; }
.google-tts-meter span:nth-child(3) { height: 64px; animation-delay: 240ms; background: var(--primary); }
.google-tts-meter span:nth-child(4) { height: 38px; animation-delay: 360ms; }
.google-tts-meter span:nth-child(5) { height: 56px; animation-delay: 480ms; }

.google-tts-workbench {
  align-items: flex-start !important;
  gap: 14px !important;
  display: grid !important;
  grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.8fr);
}

.google-main-panel,
.google-control-panel {
  gap: 12px !important;
  min-width: 0 !important;
  max-width: 100% !important;
  width: 100% !important;
}

.google-main-panel {
  flex: unset !important;
}

.google-control-panel {
  flex: unset !important;
}

.google-editor-card,
.google-result-card {
  padding: 0 !important;
  overflow: hidden;
  border-color: #d7dee8 !important;
  background: #ffffff !important;
}

.google-editor-card .tts-script-input,
.google-editor-card .tts-script-input > .form,
.google-editor-card .tts-script-input .block {
  border: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}

.google-editor-card textarea {
  height: 240px !important;
  min-height: 240px !important;
  border: 0 !important;
  border-radius: 0 !important;
  padding: 18px !important;
  color: #111827 !important;
  font-size: 17px !important;
  line-height: 1.62 !important;
  resize: vertical !important;
}

.google-editor-card > .styler,
.google-result-card > .styler {
  gap: 0 !important;
}

.google-result-card audio {
  padding: 16px 18px 4px;
}

.google-result-card textarea {
  min-height: 150px !important;
  border: 0 !important;
  border-top: 1px solid var(--line) !important;
  border-radius: 0 !important;
  background: #ffffff !important;
}

.google-private-section,
.google-voice-section,
.google-tune-section {
  background: #fbfcfe !important;
}

.google-private-section textarea,
.google-voice-section textarea,
.google-tune-section textarea {
  font-size: 13px !important;
  line-height: 1.55 !important;
}

.google-private-section p {
  margin: 0 !important;
  color: var(--muted) !important;
  font-size: 12px !important;
  line-height: 1.5 !important;
}

.google-voice-table-card table {
  border: 1px solid var(--line) !important;
}

.google-voice-table-card th {
  background: #f8fafc !important;
  color: var(--ink) !important;
  font-weight: 760 !important;
}

.google-voice-table-card td {
  color: var(--ink-soft) !important;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}

@media (max-width: 1100px) {
  .sidebar {
    position: static;
    min-height: auto;
    flex: 1 1 100% !important;
    max-width: 100% !important;
  }

  .create-control-panel {
    display: grid !important;
    grid-template-columns: 1fr !important;
    position: static;
    width: 100% !important;
    max-width: 100% !important;
  }

  .create-control-panel .create-adjust-section .form {
    grid-template-columns: 1fr !important;
  }

  .create-status-section .styler,
  .tts-mode-panel,
  .clone-mode-panel {
    grid-template-columns: 1fr !important;
  }

  .create-workbench {
    flex-direction: column !important;
  }

  .google-tts-workbench {
    flex-direction: column !important;
  }

  .google-main-panel,
  .google-control-panel {
    flex: 1 1 100% !important;
    width: 100% !important;
    max-width: 100% !important;
  }

  .main-pane {
    min-height: auto;
  }

  .page-title h1 {
    font-size: 28px;
  }

  .landing-hero {
    min-height: 390px;
  }

  .landing-hero-copy {
    padding: 38px;
  }

  .landing-hero h1 {
    font-size: 46px;
  }

  .landing-hero p {
    font-size: 16px;
  }

  .signal-panel {
    right: 20px;
    bottom: 24px;
    width: 44%;
    min-width: 260px;
    opacity: 0.74;
  }

  .landing-feature-grid,
  .landing-workflow {
    grid-template-columns: 1fr;
  }

  .create-studio-title {
    align-items: flex-start;
    flex-direction: column;
  }

  .eleven-editor-card textarea {
    height: 190px !important;
    min-height: 190px !important;
  }

  .tts-generate-bar {
    flex-wrap: wrap !important;
  }
}

@media (max-width: 720px) {
  .gradio-container {
    padding: 10px !important;
  }

  .main-pane,
  .sidebar {
    padding: 16px !important;
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    flex: 1 1 100% !important;
  }

  .studio-shell {
    flex-direction: column !important;
    align-items: stretch !important;
  }

  .brand {
    margin-bottom: 18px;
  }

  .nav-radio .wrap {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }

  .nav-radio label {
    min-height: 44px !important;
    padding: 0 9px !important;
    font-size: 14px !important;
  }

  .nav-radio input[type="radio"] {
    margin-right: 8px !important;
  }

  .create-studio-hero {
    padding: 14px;
  }

  .create-studio-title h1 {
    font-size: 28px;
  }

  .tts-editor-head,
  .tts-result-head,
  .clone-studio-head,
  .clone-result-head {
    align-items: flex-start;
    flex-direction: column;
    padding: 16px;
  }

  .tts-editor-badges {
    justify-content: flex-start;
  }

  .clone-source-row,
  .clone-settings-row,
  .clone-action-row {
    flex-direction: column !important;
    align-items: stretch !important;
  }

  .clone-source-row > .form,
  .clone-source-row > .block,
  .clone-settings-row > .form,
  .clone-settings-row > .block,
  .clone-action-row > .form,
  .clone-action-row > .block {
    width: auto !important;
    min-width: 0 !important;
  }

  .eleven-editor-card textarea {
    height: 180px !important;
    min-height: 180px !important;
    padding: 18px 16px !important;
    font-size: 16px !important;
  }

  .create-control-panel .small-actions .wrap {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }

  .eleven-options,
  .tts-generate-bar {
    flex-direction: column !important;
    align-items: stretch !important;
  }

  .tts-char-meter {
    min-width: 0 !important;
  }

  .landing-hero {
    min-height: 470px;
  }

  .landing-hero-copy {
    padding: 28px 22px;
  }

  .landing-hero h1 {
    font-size: 36px;
    line-height: 1.05;
  }

  .landing-proof span {
    width: 100%;
    justify-content: center;
  }

  .signal-panel {
    right: -28px;
    bottom: 18px;
    width: 86%;
    min-width: 0;
    padding: 14px;
    opacity: 0.34;
  }

  .voice-chip,
  .voice-meter {
    display: none;
  }

  .landing-section-heading h2,
  .workflow-copy h2 {
    font-size: 24px;
  }

  .landing-actions {
    flex-direction: column !important;
  }

  .landing-actions > .form,
  .landing-actions button {
    width: 100% !important;
  }

  .google-tts-hero {
    align-items: flex-start;
    flex-direction: column;
    padding: 18px;
  }

  .google-tts-hero h1 {
    font-size: 30px;
  }

  .google-tts-meter {
    display: none;
  }

  .google-editor-card textarea {
    height: 190px !important;
    min-height: 190px !important;
    padding: 18px 16px !important;
    font-size: 16px !important;
  }
}
"""
