# Synesthesia — Backlog für Phase 2 (User-Wunschliste vom 2026-05-08)

User-Feedback nach erstem Render: "Mischung aus galaxy und network wäre cool".
Beide Aspekte sind nebensächlich gegenüber den drei großen Erweiterungen unten.

## Big-Ticket: Interaktiver Vault-Explorer

Aktuell ist Synesthesia eine *Read-Only-Visualisierung*. Phase-2-Vision: Spielwiese
mit eingebauten Kontrollen.

### 1. UI-Panel mit Live-Parametern (Slider/Toggles)
- Knoten-Basis-Radius (0.2 bis 2.0)
- Knoten-Skalierung-mit-Degree (linear / log / aus)
- Linien-Opacity (0.02 bis 0.5)
- Layout-Spread (50 bis 300)
- Cluster-Centroid-Bias (0 = pure PCA, 1 = volle Cluster-Trennung)
- Fog-Density-Slider
- Render-Mode-Switch (galaxy / city / network) zur Laufzeit

Implementierung: lit-html oder vanilla HTML-Range-Inputs, debounced redraw.

### 2. Filter-Panel — Vault-Subsets anzeigen
- Cluster-Toggle: einzelne Cluster ein-/ausblenden
- Tag-Filter: nur Pages mit ausgewählten Frontmatter-Tags
- Date-Range: nur Pages mit mtime im gewählten Zeitraum
- Degree-Slider: nur Pages mit mind. N eingehenden/ausgehenden Links
- "Show only neighbors of X" — bei Klick auf Knoten wird die Ansicht auf
  die k-step-Nachbarschaft eingeschränkt

### 3. Custom Coloring
- Färbung wählbar nach: Cluster (jetzt) | mtime (frisch=hell, alt=dunkel) |
  Tag | Degree | semantischem Cluster (k-means auf Embeddings) | Public-Status
- Color-Palette per Dropdown wählbar (8 vorbereitete Themen)

### 4. Selektion + Bewegung
- Klick: Knoten als selektiert markieren (mehrere möglich, Ctrl+Klick)
- Selektierte Gruppe lässt sich greifen und an neue Position ziehen
- Alle Positionen (Original + manuell verschoben) werden in einer
  Vault-State-Datei gespeichert (`~/wiki/.vault-engine.layout.json`)
- "Reset Layout" stellt PCA-Default wieder her

### 5. Mix aus galaxy + network
- Das spezifisch erwähnte Feedback: User mag galaxy's leuchtende Punkte
  *und* network's Lambert-Sphäre-Klarheit
- Lösung: Render-Mode "hybrid" — Sphäre für hochverlinkte Hub-Pages
  (degree > 10), Glow-Point für die Long-Tail-Pages
- Variant-Datei wäre `hybrid.html.j2`

## Wo das hingehört

NICHT in Phase 1 — Phase 1 wurde explizit als "MVP, lokal-only, lesbar"
definiert. Die obigen Punkte gehören in einen späteren Sprint, vermutlich
nach Abschluss von Séance + Living-Portfolio.

Master-Plan-Phase: voraussichtlich Phase 10 oder 11 (siehe Master-Plan).
Vor Start dieses Sprints sollte ein eigener Spec geschrieben werden, weil
die UI-Komplexität nicht-trivial ist (lit-html, Layout-Persistence,
verschiedene Color-Algorithmen).

## Technische Notizen für später

- Aktuelle render.py erzeugt statisches HTML mit eingebettetem JSON.
  Für Live-Parameter wird das Modell bleiben, aber das Template muss
  ein deutlich größeres Control-UI bekommen.
- Drag-and-drop von Knoten erfordert raycaster-driven plane intersection
  bei mousemove. Three.js TransformControls passt nicht ganz, weil sie
  pro Mesh sind — wir brauchen Multi-Selection.
- Layout-Persistence: separates JSON neben der DB, weil Custom-Positions
  per-User sind, nicht per-Vault.
