/* GSAP animations for the workshop slides.
 *
 * A slide contains   ::: {.anim data-anim="NAME"}
 *                    :::
 * and this file draws the animation NAME into that div. It plays when the
 * slide is shown, loops, and restarts when you click on it.
 *
 * Each ANIMS entry gets the div and returns {tl, reset}: a paused GSAP
 * timeline, and a function that puts everything back to the start (text
 * changes made with tl.call() are not undone by GSAP itself).
 */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var C = {
    ink: '#1d2733', grey: '#8a94a3', light: '#e8edf4', screen: '#ffffff',
    frame: '#3b4656', gaze: '#e0352b', accent: '#2563c9', green: '#16864a',
    amber: '#d17c00', violet: '#7a3db8'
  };
  var MONO = "'DejaVu Sans Mono', 'Droid Sans Mono', Menlo, Consolas, monospace";
  var SANS = "'Source Sans Pro', 'Helvetica Neue', Arial, sans-serif";
  var ANIMS = {};

  // ---------------------------------------------------------------- helpers
  function el(tag, attrs, parent, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }

  function svgIn(box, w, h) {
    return el('svg', {viewBox: '0 0 ' + w + ' ' + h, width: '100%', height: '100%',
      preserveAspectRatio: 'xMidYMid meet', 'font-family': SANS}, box);
  }

  function screen(svg, x, y, w, h, label) {
    var g = el('g', {}, svg);
    el('rect', {x: x - 8, y: y - 8, width: w + 16, height: h + 16, rx: 14, fill: C.frame}, g);
    el('rect', {x: x, y: y, width: w, height: h, fill: C.screen}, g);
    if (label) el('text', {x: x, y: y - 18, 'font-size': 24, fill: C.grey}, g, label);
    return g;
  }

  function gazeDot(svg, x, y) {
    var g = el('g', {opacity: 0}, svg);
    var c = el('circle', {cx: x, cy: y, r: 17, fill: C.gaze, 'fill-opacity': 0.45,
      stroke: C.gaze, 'stroke-width': 3}, g);
    return {g: g, c: c};
  }

  // Draw `str` one <text> per character so that single letters can change.
  function monoLine(parent, str, x0, y, size, color) {
    var probe = el('text', {x: 0, y: -100, 'font-family': MONO, 'font-size': size}, parent,
      'MMMMMMMMMMMMMMMMMMMM');
    var cw = probe.getComputedTextLength() / 20 || size * 0.6;
    parent.removeChild(probe);
    var chars = [];
    for (var i = 0; i < str.length; i++) {
      chars.push(el('text', {x: x0 + i * cw, y: y, 'font-family': MONO, 'font-size': size,
        fill: color || C.ink}, parent, str[i]));
    }
    return {chars: chars, cw: cw, x0: x0, y: y, str: str,
      cx: function (i) { return x0 + (i + 0.5) * cw; }};
  }

  function setText(line, str) {
    for (var i = 0; i < line.chars.length; i++) line.chars[i].textContent = str[i] || ' ';
  }

  function caption(svg, x, y, size, anchor) {
    return el('text', {x: x, y: y, 'font-size': size || 30, fill: C.ink,
      'text-anchor': anchor || 'start', 'font-weight': 600}, svg, '');
  }

  // Text changes on the timeline; `reset` restores them.
  function says(tl, node, text, at) { tl.call(function () { node.textContent = text; }, null, at); }

  function box(svg, x, y, w, h, label, opts) {
    opts = opts || {};
    var g = el('g', {}, svg);
    var r = el('rect', {x: x, y: y, width: w, height: h, rx: 10, fill: opts.fill || '#fff',
      stroke: opts.stroke || C.frame, 'stroke-width': 3,
      'stroke-dasharray': opts.dashed ? '10 7' : 'none'}, g);
    var t = el('text', {x: x + w / 2, y: y + h / 2 + (opts.size || 26) * 0.35,
      'font-size': opts.size || 26, 'text-anchor': 'middle', fill: C.ink,
      'font-family': opts.mono ? MONO : SANS}, g, label);
    return {g: g, r: r, t: t};
  }

  function arrow(svg, x1, y1, x2, y2, color, width) {
    var id = 'ah' + Math.random().toString(36).slice(2);
    var defs = el('defs', {}, svg);
    var m = el('marker', {id: id, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7,
      markerHeight: 7, orient: 'auto-start-reverse'}, defs);
    el('path', {d: 'M0,0 L10,5 L0,10 z', fill: color || C.frame}, m);
    return el('line', {x1: x1, y1: y1, x2: x2, y2: y2, stroke: color || C.frame,
      'stroke-width': width || 3, 'marker-end': 'url(#' + id + ')'}, svg);
  }

  // A progress bar (for "fixate for 250 ms").
  function timer(svg, x, y, w, label) {
    var g = el('g', {opacity: 0}, svg);
    el('rect', {x: x, y: y, width: w, height: 14, rx: 7, fill: C.light}, g);
    var bar = el('rect', {x: x, y: y, width: 0, height: 14, rx: 7, fill: C.green}, g);
    el('text', {x: x + w + 12, y: y + 13, 'font-size': 22, fill: C.green, 'font-weight': 600}, g, label);
    return {g: g, bar: bar, w: w};
  }

  // ------------------------------------------- 1. fixations and saccades
  ANIMS.fixations = function (box_) {
    var svg = svgIn(box_, 1600, 560);
    screen(svg, 30, 40, 1540, 240);
    var line = monoLine(svg, 'Siempre tiene flores en casa, aun siendo alérgica al polen.', 90, 175, 40);
    var dot = gazeDot(svg, line.cx(0), 160);
    var marks = el('g', {}, svg);
    var cap = caption(svg, 30, 330, 30);
    // trace: horizontal gaze position (y axis) over time (x axis)
    var tx = 140, tw = 1400, ty = 380, th = 160;
    el('line', {x1: tx, y1: ty + th, x2: tx + tw, y2: ty + th, stroke: C.grey, 'stroke-width': 2}, svg);
    el('line', {x1: tx, y1: ty, x2: tx, y2: ty + th, stroke: C.grey, 'stroke-width': 2}, svg);
    el('text', {x: tx + tw, y: ty + th + 30, 'font-size': 22, fill: C.grey, 'text-anchor': 'end'}, svg, 'time →');
    el('text', {x: tx - 12, y: ty + 20, 'font-size': 22, fill: C.grey, 'text-anchor': 'end'}, svg, 'gaze x');
    el('text', {x: tx - 12, y: ty + 46, 'font-size': 22, fill: C.grey, 'text-anchor': 'end'}, svg, '→');

    // (character, duration in ms); one regression
    var fix = [[2, 210], [10, 250], [16, 190], [26, 280], [21, 170], [35, 230], [44, 200], [54, 260]];
    var slow = 2.6;                      // slow motion: 250 ms fixation -> 0.65 s
    var sacc = 0.12;                     // saccade duration in the animation
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2.5});
    var t = 0.4, pts = [], total = 0;
    fix.forEach(function (f) { total += f[1] / 1000 * slow + sacc; });
    var xmax = line.cx(line.str.length - 1);
    function tX(time) { return tx + time / total * tw; }
    function tY(x) { return ty + th - (x - line.x0) / (xmax - line.x0) * th; }
    tl.to(dot.g, {opacity: 1, duration: 0.2}, 0);
    says(tl, cap, 'Fixation: the eye stays still for ~200–300 ms and takes in information', 0.4);
    var prev = null, clock = 0;
    fix.forEach(function (f, i) {
      var x = line.cx(f[0]), dur = f[1] / 1000 * slow;
      if (prev !== null) {
        var back = x < prev;
        tl.to(dot.c, {attr: {cx: x}, duration: sacc, ease: 'power2.inOut'}, t);
        var s = el('line', {x1: prev, y1: 228, x2: prev, y2: 228,
          stroke: back ? C.amber : C.accent, 'stroke-width': 4, opacity: 0.8}, marks);
        tl.to(s, {attr: {x2: x}, duration: sacc}, t);
        if (i === 1) says(tl, cap, 'Saccade: a jump of ~30 ms; during it we are practically blind', t);
        if (back) {
          var lab = el('text', {x: (x + prev) / 2, y: 262, 'font-size': 22, fill: C.amber,
            'text-anchor': 'middle', opacity: 0}, marks, '← regression');
          tl.to(lab, {opacity: 1, duration: 0.2}, t);
          says(tl, cap, 'Regression: a saccade back to re-read', t);
        }
        if (i === 2) says(tl, cap, 'Each fixation: where (x, y), when, how long', t + sacc);
        pts.push([tX(clock), tY(prev)], [tX(clock + sacc), tY(x)]);
        clock += sacc;
        t += sacc;
      } else {
        pts.push([tX(0), tY(x)]);
      }
      var r = 8 + f[1] / 25;
      var circ = el('circle', {cx: x, cy: 120, r: r, fill: C.gaze, 'fill-opacity': 0.18,
        stroke: C.gaze, 'stroke-width': 2, opacity: 0}, marks);
      var ms = el('text', {x: x, y: 80, 'font-size': 22, 'text-anchor': 'middle', fill: C.gaze,
        opacity: 0}, marks, f[1] + ' ms');
      tl.to([circ, ms], {opacity: 1, duration: 0.2}, t + 0.1);
      clock += dur;
      pts.push([tX(clock), tY(x)]);
      t += dur;
      prev = x;
    });
    var trace = el('polyline', {points: pts.map(function (p) { return p.join(','); }).join(' '),
      fill: 'none', stroke: C.gaze, 'stroke-width': 4}, svg);
    var clipId = 'clip' + Math.random().toString(36).slice(2);
    var clip = el('clipPath', {id: clipId}, el('defs', {}, svg));
    var cr = el('rect', {x: tx, y: ty - 10, width: 0, height: th + 20}, clip);
    trace.setAttribute('clip-path', 'url(#' + clipId + ')');
    tl.to(cr, {attr: {width: tw}, duration: total, ease: 'none'}, 0.4);
    says(tl, cap, 'Below: the same eye movements as a trace — flat = fixation, steep = saccade', t + 0.2);
    tl.to({}, {duration: 2.5}, t + 0.2);
    function reset() { cap.textContent = ''; }
    return {tl: tl, reset: reset};
  };

  // ------------------------------------- 2. the gaze-contingent loop
  ANIMS.loop = function (box_) {
    var svg = svgIn(box_, 1600, 560);
    screen(svg, 30, 60, 860, 300, 'participant screen');
    var MASKED = 'Siempre tiene flores en casa, aun siendo ######## al polen.';
    var line = monoLine(svg, MASKED, 50, 225, 22);
    var tStart = 41, tLen = 8;
    var region = el('rect', {x: line.x0 + tStart * line.cw - 6, y: 180, width: tLen * line.cw + 12,
      height: 62, fill: 'none', stroke: C.accent, 'stroke-width': 3, 'stroke-dasharray': '10 7'}, svg);
    el('text', {x: line.x0 + tStart * line.cw, y: 290, 'font-size': 22, fill: C.accent}, svg,
      'critical region (invisible)');
    var dot = gazeDot(svg, line.cx(1), 210);
    var b1 = box(svg, 1000, 40, 560, 80, 'x, y = eyetracker.sample()', {mono: true, size: 25});
    var b2 = box(svg, 1000, 200, 560, 80, 'gaze in the region?', {size: 28});
    var b3 = box(svg, 1000, 400, 560, 80, 'new_canvas.show()', {mono: true, size: 25});
    arrow(svg, 1280, 120, 1280, 198);
    arrow(svg, 1280, 280, 1280, 398, C.green);
    el('text', {x: 1295, y: 345, 'font-size': 26, fill: C.green, 'font-weight': 700}, svg, 'yes');
    var no = el('path', {d: 'M1000,240 C930,240 930,80 998,80', fill: 'none', stroke: C.gaze,
      'stroke-width': 3}, svg);
    el('text', {x: 905, y: 170, 'font-size': 26, fill: C.gaze, 'font-weight': 700}, svg, 'no');
    var cap = caption(svg, 30, 420, 28);
    var cap2 = caption(svg, 30, 460, 24);
    cap2.setAttribute('font-weight', 400);
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2});
    tl.to(dot.g, {opacity: 1, duration: 0.2}, 0);
    says(tl, cap, 'Every few milliseconds: get a sample, check it', 0.2);
    says(tl, cap2, '(the participant sees "########" until the eyes reach the region)', 0.2);
    var fx = [2, 15, 30, 44], t = 0.4;
    function poll(at, inside) {
      tl.to(b1.r, {fill: '#dbe8ff', duration: 0.1}, at).to(b1.r, {fill: '#fff', duration: 0.1}, at + 0.25);
      tl.to(b2.r, {fill: '#dbe8ff', duration: 0.1}, at + 0.25).to(b2.r, {fill: '#fff', duration: 0.1}, at + 0.5);
      if (!inside) tl.to(no, {attr: {'stroke-width': 7}, duration: 0.1, yoyo: true, repeat: 1}, at + 0.4);
    }
    fx.forEach(function (c, i) {
      tl.to(dot.c, {attr: {cx: line.cx(c)}, duration: 0.12}, t);
      if (i < fx.length - 1) {
        poll(t + 0.15, false);
        poll(t + 0.75, false);
        t += 1.35;
      } else {
        poll(t + 0.15, true);
        tl.to(b3.r, {fill: '#d9f2e3', duration: 0.15}, t + 0.6);
        tl.to(region, {attr: {stroke: C.green}, duration: 0.15}, t + 0.6);
        tl.call(function () { setText(line, 'Siempre tiene flores en casa, aun siendo alérgica al polen.'); }, null, t + 0.7);
        says(tl, cap, 'Gaze in the region → change the display (within a few ms)', t + 0.6);
        says(tl, cap2, 'Fast because the new canvas was prepared before the trial', t + 0.6);
        t += 2.5;
      }
    });
    tl.to({}, {duration: 0.1}, t);
    function reset() {
      setText(line, MASKED);
      cap.textContent = ''; cap2.textContent = '';
    }
    return {tl: tl, reset: reset};
  };

  // --------------------------------- 3. one trial, gaze-contingent targets
  ANIMS.trial = function (box_) {
    var svg = svgIn(box_, 1600, 760);
    // participant screen: 1920 x 1080 shown at 0.55
    var S = 0.55, X0 = 30, Y0 = 70;
    function sx(x) { return X0 + x * S; }
    function sy(y) { return Y0 + y * S; }
    screen(svg, X0, Y0, 1920 * S, 1080 * S, 'participant screen');
    // log panel
    el('rect', {x: 1110, y: 62, width: 470, height: 610, rx: 12, fill: '#f4f6fa', stroke: C.light}, svg);
    el('text', {x: 1130, y: 52, 'font-size': 24, fill: C.grey}, svg, 'messages in the tracker file');
    var logY = 105, logLines = [];
    var cap = caption(svg, 30, 740, 30);
    var dot = gazeDot(svg, sx(400), sy(800));
    var fixdot = el('g', {opacity: 0}, svg);
    el('circle', {cx: sx(960), cy: sy(540), r: 14, fill: 'none', stroke: C.ink, 'stroke-width': 4}, fixdot);
    el('circle', {cx: sx(960), cy: sy(540), r: 4, fill: C.ink}, fixdot);
    var target = el('rect', {x: sx(100), y: sy(515), width: 50 * S, height: 50 * S, fill: C.ink, opacity: 0}, svg);
    var tTimer = timer(svg, sx(100), sy(580), 140, '250 ms');
    var sentence = el('g', {opacity: 0}, svg);
    var line = monoLine(sentence, 'No aprobará el curso, pese a haberse esforzado el último trimestre.',
      sx(125), sy(540) + 8, 24);
    var corner = el('g', {opacity: 0}, svg);
    el('rect', {x: sx(1728), y: sy(972), width: 192 * S, height: 108 * S, fill: C.light}, corner);
    el('rect', {x: sx(1805), y: sy(1015), width: 9, height: 9, fill: C.ink}, corner);
    var cTimer = timer(svg, sx(1600), sy(940), 60, '100 ms');
    var question = el('g', {opacity: 0}, svg);
    el('text', {x: sx(960), y: sy(470), 'font-size': 30, 'text-anchor': 'middle', 'font-family': MONO}, question, '¿Aprobará el curso?');
    el('text', {x: sx(960), y: sy(600), 'font-size': 26, 'text-anchor': 'middle', 'font-family': MONO}, question, 'SÍ          NO');
    el('text', {x: sx(960), y: sy(700), 'font-size': 22, 'text-anchor': 'middle', 'font-family': MONO, fill: C.grey}, question, '1 = SÍ   2 = NO');
    var key = el('g', {opacity: 0}, svg);
    el('rect', {x: 860, y: 520, width: 150, height: 70, rx: 10, fill: '#fff', stroke: C.ink, 'stroke-width': 3}, key);
    var keyLabel = el('text', {x: 935, y: 566, 'font-size': 30, 'text-anchor': 'middle', 'font-weight': 700}, key, 'Space');

    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2});
    function log(msg, at) {
      tl.call(function () {
        var n = logLines.length;
        logLines.push(el('text', {x: 1130, y: logY + n * 44, 'font-size': 24, 'font-family': MONO,
          fill: C.ink}, svg, msg));
      }, null, at);
    }
    // 1. drift correction
    says(tl, cap, '1 · Drift correction: look at the dot; the experimenter presses Space', 0);
    tl.to(fixdot, {opacity: 1, duration: 0.2}, 0.2);
    tl.to(dot.g, {opacity: 1, duration: 0.2}, 0.4);
    tl.to(dot.c, {attr: {cx: sx(960), cy: sy(540)}, duration: 0.3}, 0.8);
    tl.to(key, {opacity: 1, duration: 0.15}, 1.6).to(key, {opacity: 0, duration: 0.2}, 2.2);
    tl.to(fixdot, {opacity: 0, duration: 0.1}, 2.2);
    log('trial 1/138 item 2 comma', 2.4);
    // 2. gaze target
    says(tl, cap, '2 · Gaze target: the sentence appears only after 250 ms on the square', 2.4);
    tl.to(target, {opacity: 1, duration: 0.1}, 2.4);
    log('GAZE TARGET ON', 2.5);
    tl.to(dot.c, {attr: {cx: sx(125), cy: sy(540)}, duration: 0.25, ease: 'power2.inOut'}, 3.2);
    tl.to(tTimer.g, {opacity: 1, duration: 0.1}, 3.45);
    tl.to(tTimer.bar, {attr: {width: tTimer.w}, duration: 1.2, ease: 'none'}, 3.5);
    tl.to([target, tTimer.g], {opacity: 0, duration: 0.1}, 4.75);
    // 3. sentence
    tl.to([sentence, corner], {opacity: 1, duration: 0.05}, 4.75);
    log('STIMONSET', 4.8);
    log('REGION … LETTER …', 4.9);
    says(tl, cap, '3 · The sentence starts inside the square: the first fixation is on the first letter', 4.8);
    var fx = [1, 6, 12, 17, 23, 30, 36, 44, 52, 60, 64], t = 5.6;
    fx.forEach(function (c) {
      tl.to(dot.c, {attr: {cx: line.cx(c)}, duration: 0.08}, t);
      t += 0.42;
    });
    // 4. corner
    says(tl, cap, '4 · Done reading: look at the corner square for 100 ms', t);
    tl.to(dot.c, {attr: {cx: sx(1810), cy: sy(1020)}, duration: 0.25, ease: 'power2.inOut'}, t + 0.3);
    tl.to(cTimer.g, {opacity: 1, duration: 0.1}, t + 0.6);
    tl.to(cTimer.bar, {attr: {width: cTimer.w}, duration: 0.6, ease: 'none'}, t + 0.6);
    log('TRIALEND', t + 1.25);
    tl.to([sentence, corner, cTimer.g], {opacity: 0, duration: 0.1}, t + 1.3);
    t += 1.5;
    // 5. question
    says(tl, cap, '5 · Some trials: a question, answered with the keys 1 / 2', t);
    tl.to(question, {opacity: 1, duration: 0.1}, t);
    tl.to(dot.c, {attr: {cx: sx(1060), cy: sy(600)}, duration: 0.25}, t + 0.4);
    tl.call(function () { keyLabel.textContent = '2'; }, null, t + 1.2);
    tl.to(key, {opacity: 1, duration: 0.15}, t + 1.2).to(key, {opacity: 0, duration: 0.2}, t + 1.9);
    tl.to([question, dot.g], {opacity: 0, duration: 0.2}, t + 2.0);
    log('stop_trial', t + 2.1);
    says(tl, cap, 'Next trial: drift correction again', t + 2.1);
    tl.to({}, {duration: 1}, t + 2.2);
    function reset() {
      cap.textContent = ''; keyLabel.textContent = 'Space';
      logLines.forEach(function (n) { n.remove(); }); logLines = [];
    }
    return {tl: tl, reset: reset};
  };

  // ------------------------------ 4. wait_for_fixation, step by step
  ANIMS.waitfix = function (box_) {
    var svg = svgIn(box_, 1600, 600);
    var code = [
      'while True:',
      '    x, y = eyetracker.sample()',
      '    if region(x, y):',
      '        if since is None:',
      '            since = clock.time()',
      '        elif clock.time() - since >= 250:',
      "            return 'fixated'",
      '    else:',
      '        since = None'
    ];
    el('rect', {x: 20, y: 20, width: 900, height: 470, rx: 12, fill: '#f4f6fa'}, svg);
    var hl = el('rect', {x: 30, y: 40, width: 880, height: 46, rx: 6, fill: '#ffe7a3', opacity: 0}, svg);
    code.forEach(function (c, i) {
      el('text', {x: 50, y: 74 + i * 50, 'font-size': 28, 'font-family': MONO, fill: C.ink,
        style: 'white-space: pre'}, svg, c);
    });
    // right: the gaze target and the gaze
    screen(svg, 980, 60, 590, 330, 'screen');
    var sq = el('rect', {x: 1180, y: 190, width: 70, height: 70, fill: C.ink}, svg);
    el('rect', {x: 1170, y: 180, width: 90, height: 90, fill: 'none', stroke: C.accent,
      'stroke-dasharray': '8 6', 'stroke-width': 3}, svg);
    var dot = gazeDot(svg, 1450, 330);
    var since = el('text', {x: 980, y: 440, 'font-size': 28, 'font-family': MONO, fill: C.ink}, svg, 'since = None');
    var tm = timer(svg, 980, 470, 420, '');
    var tmLabel = el('text', {x: 1415, y: 483, 'font-size': 24, fill: C.green, 'font-weight': 600}, svg, '0 ms');
    var cap = caption(svg, 20, 560, 28);
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2.5});
    function line(i, at) { tl.to(hl, {attr: {y: 40 + i * 50}, opacity: 1, duration: 0.12}, at); }
    tl.to(dot.g, {opacity: 1, duration: 0.2}, 0);
    tl.to(tm.g, {opacity: 1, duration: 0.2}, 0);
    var t = 0.4;
    // gaze outside: two polls
    says(tl, cap, 'Gaze outside the square → since = None', t);
    [0, 1].forEach(function () { line(1, t); line(2, t + 0.35); line(7, t + 0.7); line(8, t + 0.9); t += 1.3; });
    // gaze enters
    tl.to(dot.c, {attr: {cx: 1215, cy: 225}, duration: 0.15}, t);
    line(1, t + 0.2); line(2, t + 0.55); line(3, t + 0.9); line(4, t + 1.2);
    says(tl, cap, 'Gaze enters → remember when (since = now)', t + 0.55);
    tl.call(function () { since.textContent = 'since = 1340'; }, null, t + 1.25);
    t += 1.6;
    line(1, t); line(2, t + 0.3); line(5, t + 0.6);
    tl.to(tm.bar, {attr: {width: 0.4 * 420}, duration: 0.6, ease: 'none'}, t);
    tl.call(function () { tmLabel.textContent = '100 ms'; }, null, t + 0.6);
    says(tl, cap, 'Still inside, but only 100 ms: keep waiting', t + 0.6);
    t += 1.3;
    // leaves: reset
    tl.to(dot.c, {attr: {cx: 1420, cy: 300}, duration: 0.15}, t);
    line(1, t + 0.2); line(2, t + 0.5); line(7, t + 0.8); line(8, t + 1.0);
    tl.to(tm.bar, {attr: {width: 0}, duration: 0.2}, t + 1.0);
    tl.call(function () { since.textContent = 'since = None'; tmLabel.textContent = '0 ms'; }, null, t + 1.05);
    says(tl, cap, 'Gaze leaves → start again: the 250 ms must be uninterrupted', t + 0.5);
    t += 1.8;
    // enters again and stays
    tl.to(dot.c, {attr: {cx: 1212, cy: 228}, duration: 0.15}, t);
    line(1, t + 0.2); line(2, t + 0.5); line(3, t + 0.8); line(4, t + 1.05);
    tl.call(function () { since.textContent = 'since = 2210'; }, null, t + 1.1);
    says(tl, cap, 'Gaze enters again → since = now', t + 0.5);
    t += 1.4;
    tl.to(tm.bar, {attr: {width: 420}, duration: 1.6, ease: 'none'}, t);
    [0, 1, 2].forEach(function (k) { line(1, t + k * 0.55); line(2, t + k * 0.55 + 0.18); line(5, t + k * 0.55 + 0.36); });
    tl.call(function () { tmLabel.textContent = '250 ms'; }, null, t + 1.6);
    line(6, t + 1.65);
    tl.to(sq, {attr: {fill: C.green}, duration: 0.2}, t + 1.7);
    says(tl, cap, "250 ms without leaving → return 'fixated' → show the sentence", t + 1.7);
    tl.to({}, {duration: 1.5}, t + 1.8);
    function reset() {
      cap.textContent = ''; since.textContent = 'since = None'; tmLabel.textContent = '0 ms';
    }
    return {tl: tl, reset: reset};
  };

  // ------------------------------------ 5. structure of the experiments
  ANIMS.structure = function (box_) {
    box_.classList.add('anim-structure');
    function row(title, items, cls) {
      var wrap = document.createElement('div');
      wrap.className = 'st-row ' + (cls || '');
      var h = document.createElement('div');
      h.className = 'st-title';
      h.textContent = title;
      wrap.appendChild(h);
      var grid = document.createElement('div');
      grid.className = 'st-grid';
      var nodes = items.map(function (it) {
        var d = document.createElement('div');
        d.className = 'st-item' + (it[1] ? ' ' + it[1] : '');
        d.textContent = it[0].replace(/_/g, '_\u200b');
        grid.appendChild(d);
        return d;
      });
      wrap.appendChild(grid);
      box_.appendChild(wrap);
      return nodes;
    }
    var exp = row('experiment (runs once)', [
      ['pygaze_init'], ['setup_helpers'], ['eyelink_setup', 'el'], ['validate_calibration'],
      ['instructions'], ['practice + experimental loops', 'loop'], ['goodbye']]);
    var counter = document.createElement('div');
    counter.className = 'st-counter';
    box_.appendChild(counter);
    var trial = row('trial_sequence (runs once for every row of the loop table)', [
      ['setup_condition'], ['prepare_trial', 'own'], ['drift_correct'], ['eyelink_trial_start', 'el'],
      ['start_recording'], ['log_trial'], ['show_gaze_target'], ['trial_display', 'own'],
      ['comprehension_question'], ['keyboard_response'], ['clear_screen'], ['logger'],
      ['stop_recording'], ['eyelink_trial_end', 'el']], 'st-trial');
    var legend = document.createElement('div');
    legend.className = 'st-legend';
    legend.innerHTML = '<span class="st-item own">different in every experiment</span>' +
      '<span class="st-item">the same in all four</span>' +
      '<span class="st-item el">EyeLink only (does nothing otherwise)</span>';
    box_.appendChild(legend);
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2});
    var t = 0.3;
    function on(n, at, d) {
      tl.to(n, {backgroundColor: '#ffe7a3', scale: 1.06, duration: 0.15}, at);
      tl.to(n, {backgroundColor: '', scale: 1, duration: 0.2}, at + (d || 0.45));
    }
    exp.slice(0, 5).forEach(function (n) { on(n, t); t += 0.55; });
    var loopNode = exp[5];
    tl.to(loopNode, {backgroundColor: '#ffe7a3', scale: 1.06, duration: 0.15}, t);
    for (var k = 1; k <= 3; k++) {
      (function (k) {
        tl.call(function () { counter.textContent = '↓ trial ' + k + ' of 138'; }, null, t);
      })(k);
      trial.forEach(function (n) { on(n, t + 0.05, 0.25); t += k === 1 ? 0.35 : 0.12; });
      t += 0.2;
    }
    tl.call(function () { counter.textContent = '… until the last row of the table'; }, null, t);
    tl.to(loopNode, {backgroundColor: '', scale: 1, duration: 0.2}, t + 0.6);
    on(exp[6], t + 0.8);
    tl.to({}, {duration: 1}, t + 1.2);
    function reset() { counter.textContent = ''; }
    return {tl: tl, reset: reset};
  };

  // --------------------------------------------------- 6. prepare / run
  ANIMS.preparerun = function (box_) {
    var svg = svgIn(box_, 1600, 330);
    var y0 = 70;
    el('text', {x: 20, y: y0 + 45, 'font-size': 28, 'font-weight': 700, fill: C.violet}, svg, 'prepare');
    el('text', {x: 20, y: y0 + 165, 'font-size': 28, 'font-weight': 700, fill: C.green}, svg, 'run');
    el('line', {x1: 160, y1: y0 + 230, x2: 1580, y2: y0 + 230, stroke: C.grey, 'stroke-width': 2}, svg);
    el('text', {x: 1580, y: y0 + 262, 'font-size': 22, fill: C.grey, 'text-anchor': 'end'}, svg, 'time →');
    var items = [['build sentence canvas', 330], ['measure letter positions', 360], ['build gaze-target canvas', 300]];
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2});
    var x = 160, t = 0.3;
    items.forEach(function (it) {
      var r = el('rect', {x: x, y: y0, width: 0, height: 70, rx: 8, fill: '#eadcf7', stroke: C.violet, 'stroke-width': 2}, svg);
      var tx = el('text', {x: x + 12, y: y0 + 44, 'font-size': 24, fill: C.ink, opacity: 0}, svg, it[0]);
      tl.to(r, {attr: {width: it[1] - 10}, duration: 0.7, ease: 'none'}, t);
      tl.to(tx, {opacity: 1, duration: 0.2}, t + 0.3);
      x += it[1]; t += 0.75;
    });
    var marks = [['show()', 0], ['GAZE TARGET ON', 0], ['show()', 150], ['STIMONSET', 150]];
    var runs = [];
    var x2 = x + 20;
    [['gaze target: show()', 200], ['sentence: show()', 200]].forEach(function (it, i) {
      var r = el('rect', {x: x2, y: y0 + 120, width: 14, height: 70, fill: C.green, opacity: 0}, svg);
      var tx = el('text', {x: x2 + 24, y: y0 + 165, 'font-size': 24, fill: C.green, opacity: 0}, svg, it[0] + ' ≈ 1 ms');
      tl.to([r, tx], {opacity: 1, duration: 0.1}, t + 0.3 + i * 0.6);
      x2 += 420;
    });
    var cap = caption(svg, 160, 30, 26);
    says(tl, cap, 'Slow work happens before the trial …', 0.3);
    says(tl, cap, '… so that the time-critical moments only need show()', t + 0.3);
    tl.to({}, {duration: 1.5}, t + 1);
    function reset() { cap.textContent = ''; }
    return {tl: tl, reset: reset};
  };

  // ------------------------------------------------ 7. boundary paradigm
  ANIMS.boundary = function (box_) {
    var svg = svgIn(box_, 1600, 520);
    screen(svg, 30, 50, 1540, 250);
    var pre = 'El arquitecto criticó el forma de trabajar del albañil.';
    var post = 'El arquitecto criticó la forma de trabajar del albañil.';
    var line = monoLine(svg, pre, 90, 190, 42);
    var bx = line.x0 + 21 * line.cw + 0.4 * line.cw;
    var bline = el('line', {x1: bx, y1: 75, x2: bx, y2: 280, stroke: C.accent, 'stroke-width': 3,
      'stroke-dasharray': '10 8'}, svg);
    el('text', {x: bx + 10, y: 100, 'font-size': 22, fill: C.accent}, svg, 'invisible boundary');
    var tbox = el('rect', {x: line.x0 + 22 * line.cw - 4, y: 140, width: 2 * line.cw + 8, height: 66,
      fill: C.amber, 'fill-opacity': 0.0, rx: 6}, svg);
    var dot = gazeDot(svg, line.cx(1), 172);
    var cap = caption(svg, 30, 350, 30);
    var cap2 = caption(svg, 30, 395, 24);
    cap2.setAttribute('font-weight', 400);
    // timing bar
    var tg = el('g', {opacity: 0}, svg);
    el('text', {x: 30, y: 470, 'font-size': 22, fill: C.grey}, tg, 'saccade');
    el('rect', {x: 130, y: 452, width: 600, height: 24, fill: '#fde2e0'}, tg);
    el('text', {x: 740, y: 470, 'font-size': 22, fill: C.grey}, tg, '≈ 30 ms');
    el('rect', {x: 130, y: 482, width: 180, height: 16, fill: C.green}, tg);
    el('text', {x: 320, y: 497, 'font-size': 20, fill: C.green}, tg, 'display change done (tracker + polling + monitor refresh)');
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2.5});
    tl.to(dot.g, {opacity: 1, duration: 0.2}, 0);
    says(tl, cap, 'Before the boundary: the target position shows a preview ("el")', 0.2);
    says(tl, cap2, 'Dissimilar preview el → la; identical preview la → la (no change)', 0.2);
    tl.to(tbox, {attr: {'fill-opacity': 0.25}, duration: 0.3}, 0.3);
    var fx = [1, 8, 16, 19], t = 0.6;
    fx.forEach(function (c) { tl.to(dot.c, {attr: {cx: line.cx(c)}, duration: 0.1}, t); t += 0.9; });
    // the crossing saccade: 19 -> 27, slowed down a lot
    var x1 = line.cx(19), x2 = line.cx(27), dur = 1.6;
    var frac = (bx - x1) / (x2 - x1);
    says(tl, cap, 'A saccade crosses the boundary (shown in slow motion) …', t);
    tl.to(dot.c, {attr: {cx: x2}, duration: dur, ease: 'none'}, t);
    tl.call(function () { setText(line, post); }, null, t + dur * frac);
    tl.to(tbox, {attr: {fill: C.green, 'fill-opacity': 0.35}, duration: 0.1}, t + dur * frac);
    tl.to(bline, {attr: {stroke: C.green}, duration: 0.1}, t + dur * frac);
    says(tl, cap, '… the display changes during the saccade: "la"', t + dur * frac);
    tl.to(tg, {opacity: 1, duration: 0.3}, t + dur * frac);
    t += dur + 0.6;
    says(tl, cap, 'The reader fixates "la" and does not notice the change', t);
    says(tl, cap2, 'Longer fixations after a dissimilar preview = the word was processed before it was fixated', t);
    [33, 40, 48, 53].forEach(function (c) { tl.to(dot.c, {attr: {cx: line.cx(c)}, duration: 0.1}, t); t += 0.8; });
    function reset() {
      setText(line, pre); cap.textContent = ''; cap2.textContent = '';
      tbox.setAttribute('fill', C.amber); bline.setAttribute('stroke', C.accent);
    }
    return {tl: tl, reset: reset};
  };

  // ------------------------------------------------- 8. moving window
  ANIMS.movingwindow = function (box_) {
    var svg = svgIn(box_, 1600, 330);
    screen(svg, 30, 40, 1540, 200);
    var s = 'Los lectores ven solo unas pocas letras alrededor de la fijación.';
    var line = monoLine(svg, s, 70, 155, 33);
    var dot = gazeDot(svg, line.cx(0), 140);
    var win = el('rect', {x: 0, y: 105, width: 0, height: 66, rx: 6, fill: C.accent, 'fill-opacity': 0.12,
      stroke: C.accent, 'stroke-width': 2}, svg);
    var cap = caption(svg, 30, 300, 30);
    function masked(centre, half) {
      return s.split('').map(function (c, i) {
        return c === ' ' || Math.abs(i - centre) <= half ? c : 'x';
      }).join('');
    }
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 1.5});
    var t = 0.2;
    tl.to(dot.g, {opacity: 1, duration: 0.2}, 0);
    [[4, 'window = 4: only 9 letters visible — reading becomes slow'],
     [12, 'window = 12: 25 letters visible — almost normal reading']].forEach(function (cfg) {
      var half = cfg[0];
      says(tl, cap, cfg[1], t);
      [2, 9, 16, 24, 31, 39, 47, 55, 62].forEach(function (c) {
        tl.to(dot.c, {attr: {cx: line.cx(c)}, duration: 0.08}, t);
        tl.set(win, {attr: {x: line.x0 + (c - half) * line.cw, width: (2 * half + 1) * line.cw}}, t + 0.08);
        tl.call(function () { setText(line, masked(c, half)); }, null, t + 0.08);
        t += half === 4 ? 0.75 : 0.5;
      });
      t += 0.8;
    });
    function reset() { setText(line, masked(0, 4)); cap.textContent = ''; }
    return {tl: tl, reset: reset};
  };

  // ------------------------- 8b. moving window: flicker vs. locked window
  ANIMS.windowlock = function (box_) {
    var svg = svgIn(box_, 1600, 600);
    var s = 'Los lectores ven solo unas pocas letras alrededor de la fijación.';
    var half = 4, b = 20;                       // fixation on the boundary 19 | 20
    function masked(centre) {
      return s.split('').map(function (c, i) {
        return c === ' ' || Math.abs(i - centre) <= half ? c : 'x';
      }).join('');
    }
    function panel(y, title, color) {
      el('text', {x: 30, y: y - 16, 'font-size': 28, 'font-weight': 700, fill: color}, svg, title);
      screen(svg, 30, y, 1540, 150);
      var line = monoLine(svg, s, 70, y + 90, 33);
      var win = el('rect', {x: 0, y: y + 45, width: (2 * half + 1) * line.cw, height: 66, rx: 6,
        fill: C.accent, 'fill-opacity': 0.12, stroke: C.accent, 'stroke-width': 2}, svg);
      var dot = gazeDot(svg, line.x0 + b * line.cw, y + 75);
      var count = el('text', {x: 1570, y: y - 16, 'font-size': 26, 'text-anchor': 'end',
        fill: color, 'font-weight': 700}, svg, '');
      return {line: line, win: win, dot: dot, count: count, n: 0, at: 19};
    }
    var A = panel(70, 'Window follows every gaze sample', C.gaze);
    var B = panel(330, 'Window locked; only a saccade (≥ 1.5 letters) moves it', C.green);
    var cap = caption(svg, 30, 585, 28);
    function place(P, c) {
      P.at = c;
      P.win.setAttribute('x', P.line.x0 + (c - half) * P.line.cw);
      setText(P.line, masked(c));
      P.count.textContent = 'window changes: ' + P.n;
    }
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2});
    tl.to([A.dot.g, B.dot.g], {opacity: 1, duration: 0.2}, 0);
    says(tl, cap, 'A fixation on the boundary between two letters; the gaze drifts across it', 0.3);
    var t = 0.6, side = -1;
    for (var i = 0; i < 40; i++) {
      var x = A.line.x0 + (b + side * 0.3) * A.line.cw;
      tl.to([A.dot.c, B.dot.c], {attr: {cx: x}, duration: 0.07, ease: 'sine.inOut'}, t);
      (function (c) {
        tl.call(function () { A.n += 1; place(A, c); }, null, t + 0.07);
      })(side < 0 ? 19 : 20);
      side = -side;
      t += 0.09;
    }
    says(tl, cap, 'Top: the window flickers back and forth. Bottom: it stays where it was locked', 1.8);
    t += 0.3;
    says(tl, cap, 'A saccade of 7 letters: both windows move to the new fixation', t);
    var x2 = A.line.cx(27);
    tl.to([A.dot.c, B.dot.c], {attr: {cx: x2}, duration: 0.08}, t);
    tl.call(function () { A.n += 1; place(A, 27); B.n += 1; place(B, 27); }, null, t + 0.08);
    tl.to({}, {duration: 2.5}, t + 0.1);
    function reset() {
      A.n = 0; B.n = 0; place(A, 19); place(B, 19);
      A.count.textContent = 'window changes: 0'; B.count.textContent = 'window changes: 0';
      cap.textContent = '';
    }
    reset();
    return {tl: tl, reset: reset};
  };

  // ------------------------------------------------- 9. visual world
  ANIMS.vwp = function (box_) {
    var svg = svgIn(box_, 1600, 700);
    screen(svg, 30, 50, 860, 560, 'participant screen');
    var cx = 460, cy = 330;
    var pos = {candle: [cx - 215, cy - 140], candy: [cx + 215, cy - 140],
      chair: [cx - 215, cy + 140], apple: [cx + 215, cy + 140]};
    for (var n in pos) {
      el('image', {href: 'images/vwp/' + n + '.png', x: pos[n][0] - 85, y: pos[n][1] - 85,
        width: 170, height: 170}, svg);
    }
    var gt = el('rect', {x: cx - 14, y: cy - 14, width: 28, height: 28, fill: C.ink}, svg);
    var dot = gazeDot(svg, cx, cy);
    var cursor = el('path', {d: 'M0,0 L0,34 L9,26 L16,42 L22,39 L15,24 L27,24 Z', fill: '#fff',
      stroke: C.ink, 'stroke-width': 2.5, opacity: 0}, svg);
    gsap.set(cursor, {x: cx + 60, y: cy + 60});
    var ripple = el('circle', {cx: pos.candle[0], cy: pos.candle[1], r: 10, fill: 'none',
      stroke: C.green, 'stroke-width': 5, opacity: 0}, svg);
    // audio + plot
    el('text', {x: 940, y: 80, 'font-size': 24, fill: C.grey}, svg, 'what the participant hears');
    var said = monoLine(svg, 'Click on the candle', 940, 130, 36);
    said.chars.forEach(function (c) { c.setAttribute('opacity', 0); c.setAttribute('font-weight', 700); });
    // character ranges of "Click", "on", "the", "cand", "le"
    var wnodes = [[0, 5], [6, 8], [9, 12], [13, 17], [17, 19]].map(function (r) {
      return said.chars.slice(r[0], r[1]);
    });
    var ox = said.x0 + 13 * said.cw;
    var onset = el('g', {opacity: 0}, svg);
    el('line', {x1: ox, y1: 145, x2: ox, y2: 175, stroke: C.gaze, 'stroke-width': 3}, onset);
    el('text', {x: ox, y: 200, 'font-size': 20, fill: C.gaze, 'text-anchor': 'middle'}, onset, 'TARGET_ONSET');
    // plot: proportion of looks, from target onset
    var px = 960, pw = 600, py = 260, ph = 300;
    el('line', {x1: px, y1: py + ph, x2: px + pw, y2: py + ph, stroke: C.grey, 'stroke-width': 2}, svg);
    el('line', {x1: px, y1: py, x2: px, y2: py + ph, stroke: C.grey, 'stroke-width': 2}, svg);
    el('text', {x: px - 10, y: py + 10, 'font-size': 20, fill: C.grey, 'text-anchor': 'end'}, svg, '1');
    el('text', {x: px - 10, y: py + ph, 'font-size': 20, fill: C.grey, 'text-anchor': 'end'}, svg, '0');
    el('text', {x: px + pw, y: py + ph + 30, 'font-size': 20, fill: C.grey, 'text-anchor': 'end'}, svg, 'ms after target onset → 1000');
    el('text', {x: px, y: py - 16, 'font-size': 22, fill: C.grey}, svg, 'proportion of looks (illustration)');
    function curve(f) {
      var p = [];
      for (var i = 0; i <= 50; i++) { var t = i / 50; p.push((px + t * pw) + ',' + (py + ph - f(t) * ph)); }
      return p.join(' ');
    }
    function sig(t, m, s) { return 1 / (1 + Math.exp(-(t - m) / s)); }
    var curves = [
      [function (t) { return 0.2 + 0.7 * sig(t, 0.45, 0.07); }, C.green, 'candle (target)', 0.88],
      [function (t) { return 0.2 + 0.28 * sig(t, 0.25, 0.05) - 0.38 * sig(t, 0.55, 0.07); }, C.amber, 'candy (competitor)', 0.38],
      [function (t) { return 0.2 - 0.15 * sig(t, 0.4, 0.08); }, C.grey, 'chair, apple', 0.1]];
    var clipId = 'vclip' + Math.random().toString(36).slice(2);
    var cr = el('rect', {x: px, y: py - 10, width: 0, height: ph + 20}, el('clipPath', {id: clipId}, el('defs', {}, svg)));
    curves.forEach(function (c) {
      el('polyline', {points: curve(c[0]), fill: 'none', stroke: c[1], 'stroke-width': 5,
        'clip-path': 'url(#' + clipId + ')'}, svg);
      var lab = el('text', {x: px + pw - 4, y: py + ph - c[3] * ph - 10, 'font-size': 20, fill: c[1],
        'text-anchor': 'end', 'font-weight': 600, opacity: 0}, svg, c[2]);
      c.push(lab);
    });
    var cap = caption(svg, 30, 670, 28);
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2});
    tl.to(dot.g, {opacity: 1, duration: 0.2}, 0);
    says(tl, cap, 'Preview: four pictures; the participant looks at the centre', 0.2);
    tl.to(gt, {opacity: 0, duration: 0.2}, 1.2);
    var t = 1.6;
    says(tl, cap, 'The spoken instruction starts (AUDIO_ONSET)', t);
    tl.to(wnodes[0], {opacity: 1, duration: 0.15}, t);
    tl.to(wnodes[1], {opacity: 1, duration: 0.15}, t + 0.4);
    tl.to(wnodes[2], {opacity: 1, duration: 0.15}, t + 0.7);
    t += 1.1;
    tl.to(wnodes[3].concat([onset]), {opacity: 1, duration: 0.15}, t);
    tl.to(cr, {attr: {width: pw}, duration: 3.2, ease: 'none'}, t);
    says(tl, cap, '"cand…" could be candle or candy: looks to both', t + 0.3);
    tl.to(dot.c, {attr: {cx: pos.candy[0], cy: pos.candy[1]}, duration: 0.12}, t + 0.6);
    tl.to(wnodes[4], {opacity: 1, duration: 0.15}, t + 1.0);
    says(tl, cap, '"…le": now it can only be the candle', t + 1.3);
    tl.to(dot.c, {attr: {cx: pos.candle[0] + 10, cy: pos.candle[1]}, duration: 0.12}, t + 1.45);
    tl.to(cursor, {opacity: 1, duration: 0.1}, t + 1.6);
    tl.to(cursor, {x: pos.candle[0] + 20, y: pos.candle[1] + 20, duration: 0.7, ease: 'power2.inOut'}, t + 1.7);
    tl.to(ripple, {opacity: 1, attr: {r: 60}, duration: 0.5}, t + 2.45).to(ripple, {opacity: 0, duration: 0.3}, t + 2.95);
    says(tl, cap, 'Click on the candle: CLICK object=candle — the trial ends', t + 2.45);
    curves.forEach(function (c) { tl.to(c[4], {opacity: 1, duration: 0.3}, t + 3.2); });
    tl.to({}, {duration: 2}, t + 3.4);
    function reset() { cap.textContent = ''; }
    return {tl: tl, reset: reset};
  };

  // ---------------------------------------- 10. counterbalancing lists
  ANIMS.lists = function (box_) {
    var svg = svgIn(box_, 1600, 560);
    var n = 6, cw = 150, ch = 64;
    el('text', {x: 40, y: 40, 'font-size': 26, fill: C.grey}, svg, 'items (both versions)');
    var lists = {A: {x: 760, label: 'List A — subjects 2, 4, 6, …'}, B: {x: 1180, label: 'List B — subjects 1, 3, 5, …'}};
    for (var k in lists) {
      el('rect', {x: lists[k].x, y: 60, width: 380, height: 450, rx: 14, fill: '#f4f6fa', stroke: C.light, 'stroke-width': 3}, svg);
      el('text', {x: lists[k].x + 190, y: 40, 'font-size': 26, 'text-anchor': 'middle', fill: C.ink, 'font-weight': 700}, svg, lists[k].label);
    }
    var chips = [];
    for (var i = 0; i < n; i++) {
      var y = 70 + i * 72;
      el('text', {x: 40, y: y + 42, 'font-size': 26, fill: C.ink}, svg, 'item ' + (i + 1));
      ['comma', 'no comma'].forEach(function (v, j) {
        el('rect', {x: 160 + j * (cw + 20), y: y, width: cw, height: ch - 10, rx: 8, fill: 'none',
          stroke: C.light, 'stroke-width': 2, 'stroke-dasharray': '6 5'}, svg);
        var g = el('g', {}, svg);
        el('rect', {x: 0, y: 0, width: cw, height: ch - 10, rx: 8, fill: j ? '#fde9c9' : '#d9e6fb',
          stroke: j ? C.amber : C.accent, 'stroke-width': 2}, g);
        el('text', {x: cw / 2, y: 36, 'font-size': 24, 'text-anchor': 'middle', fill: C.ink}, g,
          (i + 1) + (j ? ' sin coma' : ' con coma'));
        gsap.set(g, {x: 160 + j * (cw + 20), y: y});
        chips.push({g: g, item: i, comma: !j, home: [160 + j * (cw + 20), y]});
      });
    }
    var cap = caption(svg, 40, 545, 28);
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2.5});
    says(tl, cap, 'Each item has two versions; each participant may read only one', 0.2);
    var slot = {A: 0, B: 0}, t = 1.2;
    chips.forEach(function (c) {
      // list A: odd items with comma; list B: the other version
      var odd = (c.item + 1) % 2 === 1;
      var to = (c.comma === odd) ? 'A' : 'B';
      var y = 75 + slot[to] * 72;
      slot[to] += 1;
      tl.to(c.g, {x: lists[to].x + (380 - cw) / 2, y: y, duration: 0.45, ease: 'power2.inOut'}, t);
      t += 0.3;
    });
    says(tl, cap, 'Odd items with comma in list A, without in list B — and vice versa', 1.2);
    t += 0.6;
    says(tl, cap, 'Every participant: 3 with, 3 without. Every item: both versions across A + B', t);
    t += 2.2;
    // random order within each list
    says(tl, cap, 'Within a participant, the order is random (loop order = random)', t);
    ['A', 'B'].forEach(function (L) {
      var mine = chips.filter(function (c) { return ((c.comma === ((c.item + 1) % 2 === 1)) ? 'A' : 'B') === L; });
      var order = [2, 0, 5, 1, 4, 3];
      mine.forEach(function (c, i) {
        tl.to(c.g, {y: 75 + order[i] * 72, duration: 0.6, ease: 'power2.inOut'}, t);
      });
    });
    tl.to({}, {duration: 2}, t + 0.6);
    function reset() { cap.textContent = ''; }
    return {tl: tl, reset: reset};
  };

  // ------------------------------------------- 11. block-order rotation
  ANIMS.blocks = function (box_) {
    var svg = svgIn(box_, 1600, 420);
    var rows = [['subjects 1, 4, 7, …', [1, 2, 3]], ['subjects 2, 5, 8, …', [2, 3, 1]], ['subjects 3, 6, 9, …', [3, 1, 2]]];
    var colors = {1: ['#d9e6fb', C.accent], 2: ['#fde9c9', C.amber], 3: ['#d8f0e2', C.green]};
    ['first', 'middle', 'last'].forEach(function (p, j) {
      el('text', {x: 520 + j * 330 + 140, y: 40, 'font-size': 26, 'text-anchor': 'middle', fill: C.grey}, svg, p);
    });
    var cols = [0, 1, 2].map(function (j) {
      return el('rect', {x: 510 + j * 330, y: 55, width: 300, height: 300, rx: 12, fill: 'none',
        stroke: C.violet, 'stroke-width': 4, opacity: 0}, svg);
    });
    var cap = caption(svg, 30, 400, 28);
    var tl = gsap.timeline({paused: true, repeat: -1, repeatDelay: 2.5});
    rows.forEach(function (r, i) {
      var y = 70 + i * 95;
      el('text', {x: 30, y: y + 48, 'font-size': 28, fill: C.ink}, svg, r[0]);
      r[1].forEach(function (b, j) {
        var g = el('g', {opacity: 0}, svg);
        el('rect', {x: 0, y: 0, width: 280, height: 74, rx: 10, fill: colors[b][0], stroke: colors[b][1], 'stroke-width': 3}, g);
        el('text', {x: 140, y: 48, 'font-size': 28, 'text-anchor': 'middle', fill: C.ink, 'font-weight': 600}, g, 'block ' + b + ' (70)');
        gsap.set(g, {x: 520 + j * 330 + 200, y: y});
        tl.to(g, {opacity: 1, x: 520 + j * 330, duration: 0.4, ease: 'power2.out'}, 0.4 + i * 1.0 + j * 0.25);
      });
    });
    says(tl, cap, 'The block order rotates with subject_nr % 3', 0.4);
    cols.forEach(function (c, j) {
      tl.to(c, {opacity: 1, duration: 0.2}, 4 + j * 1.2).to(c, {opacity: 0, duration: 0.2}, 4.9 + j * 1.2);
    });
    says(tl, cap, 'Every block is read once first, once in the middle, once last', 4);
    says(tl, cap, '× 2 preview lists = 6 versions: recruit in multiples of 6', 7.8);
    tl.to({}, {duration: 2}, 8);
    function reset() { cap.textContent = ''; }
    return {tl: tl, reset: reset};
  };

  // ------------------------------------------------------------ driver
  function start(slide) {
    if (!slide || typeof gsap === 'undefined') return;
    slide.querySelectorAll('.anim').forEach(function (b) {
      if (!b._anim) {
        var make = ANIMS[b.dataset.anim];
        if (!make) { b.textContent = 'unknown animation: ' + b.dataset.anim; return; }
        b._anim = make(b);
        b._anim.tl.eventCallback('onRepeat', b._anim.reset);
        b.addEventListener('click', function () { b._anim.reset(); b._anim.tl.restart(); });
        b.title = 'click to replay';
      }
      b._anim.reset();
      b._anim.tl.restart();
    });
  }
  function stop(slide) {
    if (!slide) return;
    slide.querySelectorAll('.anim').forEach(function (b) { if (b._anim) b._anim.tl.pause(0); });
  }
  function init() {
    if (window.Reveal && Reveal.isReady && Reveal.isReady()) start(Reveal.getCurrentSlide());
    else if (window.Reveal) Reveal.on('ready', function (e) { start(e.currentSlide); });
    if (window.Reveal) Reveal.on('slidechanged', function (e) { stop(e.previousSlide); start(e.currentSlide); });
  }
  if (document.readyState === 'complete') init(); else window.addEventListener('load', init);
  window.workshopAnimations = ANIMS;     // for testing
})();
