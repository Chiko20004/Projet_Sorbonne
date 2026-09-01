/* Fond animé du hero d'accueil : lignes ondulantes réactives à la souris,
 * dans les tons bleu électrique -> lavande de la direction artistique
 * "Nébuleuse". Portage vanilla JS (canvas 2D) d'un effet fourni en
 * React/framer-motion — pas de dépendance ajoutée, cohérent avec le choix
 * HTMX + JS vanilla du reste du site.
 */
(function () {
  var canvas = document.getElementById("hero-waveform");
  if (!canvas || !canvas.getContext) return;

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var ctx = canvas.getContext("2d");
  var mouse = { x: -9999, y: -9999 };
  var time = 0;
  var frameId = null;
  var dpr = Math.min(window.devicePixelRatio || 1, 2);

  function resize() {
    var rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + "px";
    canvas.style.height = rect.height + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function lineColor(progress) {
    // Dégradé bleu électrique -> lavande le long des lignes, intensité en cloche.
    var intensity = Math.sin(progress * Math.PI);
    var r = Math.round(59 + (201 - 59) * progress);
    var g = Math.round(59 + (160 - 59) * progress);
    var b = Math.round(240 + (242 - 240) * progress);
    return "rgba(" + r + "," + g + "," + b + "," + (intensity * 0.5) + ")";
  }

  function draw() {
    var w = canvas.width / dpr;
    var h = canvas.height / dpr;
    ctx.fillStyle = "rgba(7, 6, 12, 0.16)";
    ctx.fillRect(0, 0, w, h);

    var lineCount = 34;
    var segmentCount = 64;
    var midY = h / 2;

    for (var i = 0; i < lineCount; i++) {
      ctx.beginPath();
      var progress = i / lineCount;
      ctx.strokeStyle = lineColor(progress);
      ctx.lineWidth = 1.25;

      for (var j = 0; j <= segmentCount; j++) {
        var x = (j / segmentCount) * w;
        var distToMouse = Math.hypot(x - mouse.x, midY - mouse.y);
        var mouseEffect = Math.max(0, 1 - distToMouse / 380);

        var noise = Math.sin(j * 0.12 + time + i * 0.22) * 14;
        var spike = Math.cos(j * 0.2 + time + i * 0.12) * Math.sin(j * 0.06 + time) * 34;
        var y = midY + noise + spike * (1 + mouseEffect * 1.8);

        if (j === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    time += 0.016;
    frameId = requestAnimationFrame(draw);
  }

  function handleMouseMove(e) {
    var rect = canvas.getBoundingClientRect();
    mouse.x = e.clientX - rect.left;
    mouse.y = e.clientY - rect.top;
  }

  window.addEventListener("resize", resize);
  resize();

  if (reduceMotion) {
    // Une seule image statique, pas de boucle d'animation ni de suivi souris.
    ctx.fillStyle = "rgba(7, 6, 12, 1)";
    ctx.fillRect(0, 0, canvas.width / dpr, canvas.height / dpr);
    draw();
    cancelAnimationFrame(frameId);
  } else {
    canvas.addEventListener("mousemove", handleMouseMove);
    draw();
  }
})();
