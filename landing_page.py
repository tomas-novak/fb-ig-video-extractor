"""Static landing page for GET / – a dry, self-aware "nothing to see here" notice.

There is no product behind this domain, just a Telegram bot's webhook and a
token-gated map, so the root path exists only to give human (and bot) visitors
something less bleak than a bare 404.
"""

LANDING_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<meta name="color-scheme" content="dark">
<title>nothing to see here</title>
<link rel="icon" href="/icon-192.png" type="image/png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Stencil:wght@700;900&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<style>
  :root {
    --asphalt: #121212;
    --asphalt-2: #1a1a1a;
    --hazard: #f4c21e;
    --stamp-red: #c1392b;
    --paper: #ededea;
    --muted: #8d8a82;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    min-height: 100%;
    background: var(--asphalt);
    color: var(--paper);
    font-family: 'Space Mono', ui-monospace, monospace;
    overflow-x: hidden;
  }
  body {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 56px 20px;
    position: relative;
    background:
      radial-gradient(ellipse 900px 600px at 50% 20%, #1f1f1f 0%, var(--asphalt) 65%);
  }
  /* fine grain, purely decorative, self-contained */
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    opacity: .05;
    mix-blend-mode: overlay;
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
  }
  .hazard {
    position: fixed;
    left: 0; right: 0;
    height: 22px;
    background: repeating-linear-gradient(135deg, var(--hazard) 0 22px, var(--asphalt-2) 22px 44px);
    box-shadow: 0 0 0 1px rgba(0,0,0,.4);
    z-index: 5;
  }
  .hazard.top { top: 0; }
  .hazard.bottom { bottom: 0; }

  main {
    position: relative;
    max-width: 640px;
    text-align: center;
  }

  .kicker {
    display: inline-block;
    font-size: 12px;
    letter-spacing: .28em;
    text-transform: uppercase;
    color: var(--hazard);
    border: 1px solid rgba(244,194,30,.4);
    padding: 5px 12px;
    border-radius: 999px;
    opacity: 0;
    animation: rise .6s ease-out .1s forwards;
  }

  h1 {
    font-family: 'Big Shoulders Stencil', sans-serif;
    font-weight: 900;
    font-size: clamp(48px, 11vw, 108px);
    line-height: .92;
    letter-spacing: .01em;
    margin: 18px 0 22px;
    color: var(--paper);
    text-shadow: 0 0 40px rgba(244,194,30,.15);
    opacity: 0;
    animation: rise .7s ease-out .25s forwards;
  }
  h1 em {
    font-style: normal;
    color: var(--hazard);
  }

  p.lede {
    font-size: 15px;
    line-height: 1.7;
    color: #cfccc4;
    margin: 0 auto 26px;
    max-width: 46ch;
    opacity: 0;
    animation: rise .7s ease-out .42s forwards;
  }

  .status {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px 14px;
    justify-content: center;
    font-size: 12px;
    color: var(--muted);
    border-top: 1px dashed #3a3a38;
    border-bottom: 1px dashed #3a3a38;
    padding: 10px 4px;
    margin-bottom: 34px;
    opacity: 0;
    animation: rise .7s ease-out .58s forwards;
  }
  .status b { color: #b7c9a8; font-weight: 700; }

  .stamp {
    position: absolute;
    top: -46px;
    right: -18px;
    border: 3px double var(--stamp-red);
    color: var(--stamp-red);
    font-family: 'Big Shoulders Stencil', sans-serif;
    font-weight: 700;
    font-size: 20px;
    letter-spacing: .12em;
    padding: 7px 14px 5px;
    transform: rotate(-11deg) scale(1.4);
    opacity: 0;
    mix-blend-mode: multiply;
    filter: saturate(1.3);
    animation: stamp-in .5s cubic-bezier(.2,1.4,.4,1) 1s forwards;
  }

  .terminal {
    font-size: 12px;
    color: #79c07c;
    opacity: 0;
    animation: rise .5s ease-out 1.3s forwards;
  }
  .terminal::after {
    content: "_";
    animation: blink 1s steps(1) infinite;
  }

  @keyframes rise {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes stamp-in {
    0%   { opacity: 0; transform: rotate(-11deg) scale(2.2); }
    60%  { opacity: .9; }
    100% { opacity: .85; transform: rotate(-11deg) scale(1); }
  }
  @keyframes blink {
    50% { opacity: 0; }
  }

  @media (max-width: 480px) {
    .stamp { top: -34px; right: 4px; transform: rotate(-11deg) scale(1); }
  }
</style>
</head>
<body>
  <div class="hazard top"></div>
  <div class="hazard bottom"></div>
  <main>
    <div class="stamp">PRIVATE</div>
    <span class="kicker">Notice &middot; Private Infrastructure</span>
    <h1>NOTHING TO<br><em>SEE HERE</em></h1>
    <p class="lede">
      This address does not serve a public site. There is no product, no
      sign-up form, and nothing behind this door that was meant for you.
    </p>
    <div class="status">
      <span>ACCESS: <b>private</b></span>
      <span>PUBLIC CONTENT: <b>none</b></span>
    </div>
    <div class="terminal">&gt; there is nothing to find here</div>
  </main>
</body>
</html>"""
