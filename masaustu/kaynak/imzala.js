/**
 * Paketlemeden sonra macOS paketini AD-HOC imzala.
 *
 * NEDEN: `identity: null` ile electron-builder imzalamayı tümüyle atlıyor.
 * Paket yeniden adlandırıldığı için (Electron.app → BERNZ Studio.app) içerideki
 * eski imza artık tutmuyor ve macOS indirilen uygulamaya
 * "hasar görmüş, Çöp Sepeti'ne taşıyın" diyor — karantina bayrağı olan her
 * indirmede. Yerelde çalışması yanıltıcı: Gatekeeper yalnız karantinalı
 * dosyada devreye giriyor.
 *
 * `codesign --force --deep --sign -` bütün ikili dosyaları tutarlı bir ad-hoc
 * imzayla yeniden imzalar. Uyarı yine çıkar ("geliştirici doğrulanamadı") ama
 * uygulama AÇILABİLİR hale gelir. Uyarıyı tümden kaldırmak için Developer ID
 * sertifikası + notarization gerekir (ücretli Apple hesabı).
 */
const { execFileSync } = require('child_process')
const path = require('path')

exports.default = async function imzala(context) {
  if (context.electronPlatformName !== 'darwin') return
  const ad = context.packager.appInfo.productFilename
  const yol = path.join(context.appOutDir, `${ad}.app`)
  execFileSync('codesign', ['--force', '--deep', '--sign', '-', yol], { stdio: 'inherit' })
  // Doğrula: tutarsız imza sessizce geçmesin
  execFileSync('codesign', ['--verify', '--deep', '--strict', yol], { stdio: 'inherit' })
  console.log(`  • ad-hoc imzalandı ve doğrulandı  ${ad}.app`)
}
