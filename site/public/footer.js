/* Shared Slashy-branded site footer. Injected into <footer id="site-footer">.
   Single source of truth so the four pages stay in sync. Social accounts, links
   and the mark match slashyemail's own landing footer. */
(function () {
  var el = document.getElementById('site-footer');
  if (!el) return;
  el.innerHTML = [
    '<div class="foot-in">',
      '<div class="foot-brand">',
        '<div class="b">',
          '<svg class="mark" viewBox="0 0 664 664" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">',
            '<path d="M150 506L261.435 152H305.697L194.25 506H150Z" fill="url(#sgF)"/>',
            '<path d="M247.982 506L359.418 152H403.679L292.232 506H247.982Z" fill="url(#sgF)"/>',
            '<path d="M349.125 506L460.56 152H504.822L393.375 506H349.125Z" fill="url(#sgF)"/>',
            '<defs><linearGradient id="sgF" x1="332" y1="152" x2="332" y2="506" gradientUnits="userSpaceOnUse">',
            '<stop stop-color="#8EA1E2"/><stop offset="1" stop-color="#4457C4"/></linearGradient></defs>',
          '</svg>',
          '<span class="wm">The Slop Index</span>',
        '</div>',
        '<p><a href="https://slashy.com" target="_blank" rel="noopener">A research project from Slashy</a>, the email client that saves you time instead of generating more AI slop.</p>',
        '<div class="social">',
          '<a href="https://www.instagram.com/slashy.ai/" target="_blank" rel="noopener" aria-label="Slashy on Instagram"><svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path fill-rule="evenodd" clip-rule="evenodd" d="M9 1.621c2.405 0 2.689.011 3.635.053.879.039 1.354.186 1.67.309.418.162.721.359 1.034.671.316.316.51.615.675 1.034.123.316.271.795.309 1.67.042.949.053 1.234.053 3.635s-.011 2.689-.053 3.635c-.039.879-.186 1.354-.309 1.67a2.802 2.802 0 01-.671 1.034c-.316.316-.615.51-1.034.675-.316.123-.795.271-1.67.309-.949.042-1.234.053-3.635.053s-2.689-.011-3.635-.053c-.879-.039-1.354-.186-1.67-.309a2.802 2.802 0 01-1.034-.671 2.815 2.815 0 01-.675-1.034c-.123-.316-.271-.795-.309-1.67-.042-.949-.053-1.234-.053-3.635s.011-2.689.053-3.635c.039-.879.186-1.354.309-1.67.162-.418.359-.721.671-1.034.316-.316.615-.51 1.034-.675.316-.123.795-.271 1.67-.309.946-.042 1.23-.053 3.635-.053zM9 0C6.557 0 6.251.011 5.291.053 4.335.095 3.677.25 3.108.471a4.389 4.389 0 00-1.596 1.041A4.404 4.404 0 00.471 3.105C.25 3.678.095 4.332.053 5.288.011 6.251 0 6.557 0 9c0 2.443.011 2.749.053 3.709.042.956.197 1.614.418 2.183a4.389 4.389 0 001.041 1.596 4.392 4.392 0 001.593 1.037c.573.221 1.227.376 2.183.418.96.042 1.266.053 3.709.053s2.749-.011 3.709-.053c.956-.042 1.614-.197 2.183-.418a4.413 4.413 0 001.593-1.037c.5-.499.809-1.002 1.037-1.593.221-.573.376-1.227.418-2.183.042-.96.053-1.266.053-3.709s-.011-2.749-.053-3.709c-.042-.956-.197-1.614-.418-2.183a4.21 4.21 0 00-1.03-1.6A4.392 4.392 0 0014.896.474c-.573-.221-1.227-.376-2.183-.418C11.75.01 11.444 0 9 0zm0 4.377A4.625 4.625 0 004.377 9 4.625 4.625 0 009 13.623 4.625 4.625 0 0013.623 9 4.625 4.625 0 009 4.377zm0 7.622A3 3 0 119 6 3 3 0 019 12zm4.806-6.726a1.079 1.079 0 100-2.158 1.079 1.079 0 000 2.158z"/></svg></a>',
          '<a href="https://x.com/slashyemail" target="_blank" rel="noopener" aria-label="Slashy on X"><svg width="18" height="16" viewBox="0 0 15 13" aria-hidden="true"><path d="M11.787.523h2.109L9.289 5.788l5.42 7.164h-4.244L7.142 8.607 3.34 12.952H1.23l4.927-5.631L.958.523H5.31l3.004 3.972L11.787.523Zm-.74 11.167h1.169L4.674 1.719H3.421l7.626 9.971Z"/></svg></a>',
          '<a href="https://www.linkedin.com/company/slashy-email/" target="_blank" rel="noopener" aria-label="Slashy on LinkedIn"><svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true"><path d="M14.81 0H1.18C.53 0 0 .52 0 1.15v13.69C0 15.48.53 16 1.18 16h13.63c.65 0 1.18-.52 1.18-1.15V1.15c0-.64-.53-1.15-1.18-1.15ZM4.75 13.63H2.38V5.99h2.37v7.64ZM3.56 4.96c-.76 0-1.38-.62-1.38-1.37s.62-1.37 1.38-1.37 1.37.62 1.37 1.37-.62 1.37-1.37 1.37Zm10.07 8.67h-2.37V9.92c0-.88-.02-2.02-1.23-2.02s-1.42.97-1.42 1.96v3.77H6.24V5.99h2.27v1.04h.03c.32-.6 1.09-1.23 2.24-1.23 2.4 0 2.85 1.58 2.85 3.64v4.19Z"/></svg></a>',
          '<a href="https://www.youtube.com/@slashyaicompany" target="_blank" rel="noopener" aria-label="Slashy on YouTube"><svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M9 2.07c-8.845 0-9 .787-9 6.93s.155 6.93 9 6.93 9-.787 9-6.93-.155-6.93-9-6.93zM11.884 9.301l-4.041 1.886c-.354.164-.644-.02-.644-.41V7.224c0-.39.29-.574.644-.41l4.041 1.886c.354.166.354.436 0 .601z"/></svg></a>',
        '</div>',
        '<p class="copy">© 2026 Slashy, Inc.</p>',
      '</div>',
      '<div class="foot-col">',
        '<h4>The Slop Index</h4>',
        '<a href="/leaderboard">Leaderboard</a>',
        '<a href="/arena">Play the arena</a>',
        '<a href="/methodology">Methodology</a>',
        '<a href="/stats">Live votes</a>',
        '<a href="https://github.com/hgaddipati1118/slop-index" target="_blank" rel="noopener">Code &amp; data</a>',
      '</div>',
      '<div class="foot-col">',
        '<h4>Slashy</h4>',
        '<a href="https://slashy.com" target="_blank" rel="noopener">Home</a>',
        '<a href="https://www.slashy.com/blog/" target="_blank" rel="noopener">Blog</a>',
        '<a href="https://help.slashy.com" target="_blank" rel="noopener">Help center</a>',
        '<a href="https://cal.com/slashy/onboarding" target="_blank" rel="noopener">Book a call</a>',
      '</div>',
    '</div>',
    '<div class="foot-legal">18 models · 112 scenarios · 19,928 generations · fully open-sourced. A research project from Slashy, the email client for people who read a lot of email.</div>'
  ].join('');
})();
