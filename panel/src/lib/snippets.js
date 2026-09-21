// Hazır kod parçacıkları — tema editöründeki "Özel Kod" alanlarına tek tıkla
// eklenir. Hepsi bağımsız çalışır (dış kütüphane yok), mobil uyumludur ve
// gösterim sıklığı localStorage ile sınırlanır (müşteriyi bunaltmaz).
//
// KUPON KODLARI: çark/pop-up gerçek kod üretmez — panelde oluşturduğunuz
// kuponu gösterir. Önce İndirimler sayfasından kuponu oluşturun, sonra
// koda yapıştırın (yoksa müşteri geçersiz kod alır).

export const SNIPPETS = [
  {
    key: 'wheel',
    label: '🎡 İndirim Çarkı',
    target: 'body_html',
    hint: 'Ziyaretçi 8 saniye sonra çarkı görür, çevirir, kupon kodunu kazanır. '
        + 'Kodları İndirimler sayfasından oluşturup aşağıdaki KUPONLAR listesine yazın.',
    code: `<!-- İndirim çarkı — kodları kendi kuponlarınızla değiştirin -->
<div id="bz-wheel-wrap" style="display:none">
  <div id="bz-wheel-bg"></div>
  <div id="bz-wheel-box">
    <button id="bz-wheel-x" aria-label="Kapat">×</button>
    <h3>Şansını dene! 🎁</h3>
    <p>Çarkı çevir, indirim kodunu kap.</p>
    <div id="bz-wheel-outer">
      <div id="bz-wheel-pin"></div>
      <canvas id="bz-wheel" width="260" height="260"></canvas>
    </div>
    <button id="bz-wheel-go">ÇEVİR</button>
    <div id="bz-wheel-result"></div>
  </div>
</div>
<style>
#bz-wheel-bg{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9998}
#bz-wheel-box{position:fixed;z-index:9999;top:50%;left:50%;transform:translate(-50%,-50%);
  background:#fff;border-radius:20px;padding:22px;width:min(92vw,330px);text-align:center;
  font-family:inherit;box-shadow:0 20px 60px rgba(0,0,0,.3)}
#bz-wheel-box h3{margin:0 0 4px;font-size:19px}
#bz-wheel-box p{margin:0 0 12px;font-size:13px;color:#666}
#bz-wheel-x{position:absolute;top:8px;right:12px;border:0;background:none;font-size:26px;
  line-height:1;cursor:pointer;color:#999}
#bz-wheel-outer{position:relative;display:inline-block}
#bz-wheel-pin{position:absolute;top:-6px;left:50%;transform:translateX(-50%);
  border-left:9px solid transparent;border-right:9px solid transparent;
  border-top:17px solid #111;z-index:2}
#bz-wheel{transition:transform 4.5s cubic-bezier(.17,.67,.12,1)}
#bz-wheel-go{margin-top:14px;width:100%;padding:12px;border:0;border-radius:12px;
  background:#111;color:#fff;font-weight:600;font-size:15px;cursor:pointer}
#bz-wheel-go:disabled{opacity:.5;cursor:default}
#bz-wheel-result{margin-top:12px;font-size:15px;font-weight:600;min-height:22px}
#bz-wheel-result code{background:#f3f4f6;padding:3px 10px;border-radius:8px;
  letter-spacing:1px;user-select:all}
</style>
<script>
(function(){
  // ── DÜZENLEYİN: dilim yazısı + panelde OLUŞTURDUĞUNUZ kupon kodu ──
  var KUPONLAR = [
    { yazi: '%10 İNDİRİM', kod: 'CARK10' },
    { yazi: 'Tekrar dene', kod: null },
    { yazi: '%15 İNDİRİM', kod: 'CARK15' },
    { yazi: 'Ücretsiz Kargo', kod: 'KARGOBEDAVA' },
    { yazi: '%5 İNDİRİM', kod: 'CARK5' },
    { yazi: 'Tekrar dene', kod: null }
  ];
  var GECIKME_SN = 8;        // kaç saniye sonra açılsın
  var TEKRAR_GUN = 7;        // kazanan tekrar kaç gün görmesin

  var KEY = 'bz_wheel_seen';
  try {
    var last = localStorage.getItem(KEY);
    if (last && (Date.now() - Number(last)) < TEKRAR_GUN * 864e5) return;
  } catch(e){}

  var C = ['#111827','#dc2626','#0f766e','#b45309','#4338ca','#be185d'];
  var wrap = document.getElementById('bz-wheel-wrap');
  var canvas = document.getElementById('bz-wheel');
  var ctx = canvas.getContext('2d');
  var n = KUPONLAR.length, ang = 2*Math.PI/n, R = 130;

  KUPONLAR.forEach(function(k,i){
    ctx.beginPath(); ctx.moveTo(R,R);
    ctx.arc(R,R,R,i*ang - Math.PI/2, (i+1)*ang - Math.PI/2);
    ctx.fillStyle = C[i % C.length]; ctx.fill();
    ctx.save(); ctx.translate(R,R); ctx.rotate((i+0.5)*ang - Math.PI/2);
    ctx.fillStyle='#fff'; ctx.font='bold 11px sans-serif'; ctx.textAlign='right';
    ctx.fillText(k.yazi, R-14, 4); ctx.restore();
  });

  setTimeout(function(){ wrap.style.display='block'; }, GECIKME_SN*1000);

  function kapat(){
    wrap.style.display='none';
    try { localStorage.setItem(KEY, String(Date.now())); } catch(e){}
  }
  document.getElementById('bz-wheel-x').onclick = kapat;
  document.getElementById('bz-wheel-bg').onclick = kapat;

  var donuldu = false;
  document.getElementById('bz-wheel-go').onclick = function(){
    if (donuldu) return; donuldu = true;
    this.disabled = true;
    var i = Math.floor(Math.random()*n);
    var derece = 360*6 + (360 - (i*(360/n) + (360/n)/2));
    canvas.style.transform = 'rotate(' + derece + 'deg)';
    setTimeout(function(){
      var k = KUPONLAR[i], el = document.getElementById('bz-wheel-result');
      if (k.kod) {
        el.innerHTML = k.yazi + '<br><code>' + k.kod + '</code>';
        try { localStorage.setItem(KEY, String(Date.now())); } catch(e){}
      } else {
        el.textContent = 'Bu sefer olmadı 😊';
        try { localStorage.setItem(KEY, String(Date.now() - 6*864e5)); } catch(e){}
      }
    }, 4600);
  };
})();
</script>`,
  },
  {
    key: 'exit_popup',
    label: '🚪 Çıkışta Yakala (exit-intent)',
    target: 'body_html',
    hint: 'Ziyaretçi sekmeyi kapatmak için imleci yukarı taşıdığında indirim '
        + 'teklifi gösterir. Sepeti terk edecek müşteriyi son anda yakalar.',
    code: `<!-- Çıkış niyeti pop-up'ı — kodu kendi kuponunuzla değiştirin -->
<div id="bz-exit" style="display:none">
  <div id="bz-exit-bg"></div>
  <div id="bz-exit-box">
    <button id="bz-exit-x" aria-label="Kapat">×</button>
    <h3>Gitmeden önce… 🎁</h3>
    <p>Bu siparişe özel <b>%10 indirim</b> hazırladık.</p>
    <code id="bz-exit-code">HEMENAL10</code>
    <button id="bz-exit-cta">Kodu Kullan</button>
    <button id="bz-exit-no">Hayır, teşekkürler</button>
  </div>
</div>
<style>
#bz-exit-bg{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9998}
#bz-exit-box{position:fixed;z-index:9999;top:50%;left:50%;transform:translate(-50%,-50%);
  background:#fff;border-radius:20px;padding:26px 22px;width:min(92vw,340px);
  text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.3)}
#bz-exit-box h3{margin:0 0 6px;font-size:20px}
#bz-exit-box p{margin:0 0 14px;font-size:14px;color:#555}
#bz-exit-code{display:block;background:#f3f4f6;padding:10px;border-radius:10px;
  font-size:18px;font-weight:700;letter-spacing:2px;user-select:all}
#bz-exit-cta{margin-top:14px;width:100%;padding:12px;border:0;border-radius:12px;
  background:#111;color:#fff;font-weight:600;font-size:15px;cursor:pointer}
#bz-exit-no{margin-top:8px;border:0;background:none;color:#999;font-size:12px;cursor:pointer}
#bz-exit-x{position:absolute;top:8px;right:12px;border:0;background:none;font-size:26px;
  line-height:1;cursor:pointer;color:#999}
</style>
<script>
(function(){
  var KEY='bz_exit_seen', GUN=3;
  try { var l=localStorage.getItem(KEY);
        if(l && Date.now()-Number(l) < GUN*864e5) return; } catch(e){}
  var el = document.getElementById('bz-exit');
  function ac(){
    if (el.style.display === 'block') return;
    el.style.display='block';
    try { localStorage.setItem(KEY, String(Date.now())); } catch(e){}
  }
  function kapat(){ el.style.display='none'; }
  // Masaüstü: imleç sayfanın üstünden çıkarken
  document.addEventListener('mouseout', function(e){
    if (!e.relatedTarget && e.clientY < 10) ac();
  });
  // Mobil: 45 saniye sonra (imleç yok)
  if (matchMedia('(max-width:768px)').matches) setTimeout(ac, 45000);
  document.getElementById('bz-exit-x').onclick = kapat;
  document.getElementById('bz-exit-bg').onclick = kapat;
  document.getElementById('bz-exit-no').onclick = kapat;
  document.getElementById('bz-exit-cta').onclick = function(){
    var kod = document.getElementById('bz-exit-code').textContent.trim();
    location.href = '/sepet?kupon=' + encodeURIComponent(kod);
  };
})();
</script>`,
  },
  {
    key: 'css_examples',
    label: '🎨 Sık Kullanılan CSS',
    target: 'css',
    hint: 'Vitrinde ince ayar örnekleri — gerekmeyen satırları silin.',
    code: `/* Ürün kartlarının köşelerini keskinleştir */
/* .grid > a > div { border-radius: 6px !important; } */

/* Sepete Ekle butonunu büyüt */
/* button { font-size: 16px !important; padding: 14px !important; } */

/* Duyuru şeridini kalınlaştır */
/* header + div { padding: 10px 0 !important; font-weight: 600; }  */

/* Ürün başlıklarını tek satırda tut */
/* h3 { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; } */

/* Mobilde ürün ızgarasını tek sütuna indir */
/* @media (max-width: 480px) { .grid-cols-2 { grid-template-columns: 1fr !important; } } */`,
  },
]
