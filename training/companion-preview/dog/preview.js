const pet = document.getElementById('pet');
const follow = document.getElementById('follow');
const status = document.getElementById('status');
const poses = [...document.querySelectorAll('.pose')];
const controls = [...document.querySelectorAll('[data-pose]')];
const labels = ['看着你', '向左看看', '向右看看', '抬头看看', '低头看看', '被你摸摸，好开心'];
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
let current = 0, happyUntil = 0, pending = false, lastPointer = null, timer;
function showPose(index) {
  if (current !== index) {
    poses[current].classList.remove('visible');
    poses[index].classList.add('visible');
    current = index;
  }
  controls.forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.pose) === index)));
  status.textContent = labels[index];
}
function resetOffset() {
  pet.style.setProperty('--dx', '0px'); pet.style.setProperty('--dy', '0px');
}
function manualPose(index) {
  clearTimeout(timer); happyUntil = 0; pet.classList.remove('happy'); resetOffset();
  follow.checked = false; showPose(index);
}
function pat() {
  clearTimeout(timer); happyUntil = Date.now() + 1600;
  resetOffset(); showPose(5); pet.classList.remove('happy');
  // Restart the short reaction on repeated clicks.
  void pet.offsetWidth; pet.classList.add('happy');
  timer = setTimeout(() => { happyUntil = 0; pet.classList.remove('happy'); showPose(0); }, 1600);
}
function pointAt(clientX, clientY) {
  if (!follow.checked || Date.now() < happyUntil || pet.disabled) return;
  const box = pet.getBoundingClientRect();
  const x = (clientX - box.left - box.width / 2) / Math.max(180, box.width * .85);
  const y = (clientY - box.top - box.height * .35) / Math.max(180, box.height * .85);
  // A wider neutral band when returning to center prevents edge flicker.
  const threshold = current === 0 ? .38 : .27;
  const next = Math.max(Math.abs(x), Math.abs(y)) < threshold ? 0 : Math.abs(x) > Math.abs(y) ? (x < 0 ? 1 : 2) : (y < 0 ? 3 : 4);
  showPose(next);
  if (!reducedMotion.matches) {
    pet.style.setProperty('--dx', `${Math.max(-2, Math.min(2, x * 2))}px`);
    pet.style.setProperty('--dy', `${Math.max(-1, Math.min(1, y))}px`);
  }
}
document.addEventListener('pointermove', event => {
  if (event.pointerType === 'touch') return;
  lastPointer = [event.clientX, event.clientY];
  if (pending) return;
  pending = true;
  requestAnimationFrame(() => { pending = false; pointAt(...lastPointer); });
});
function rest() { if (Date.now() >= happyUntil && follow.checked) { resetOffset(); showPose(0); } }
document.documentElement.addEventListener('pointerleave', rest);
window.addEventListener('blur', rest);
follow.addEventListener('change', () => { clearTimeout(timer); happyUntil = 0; pet.classList.remove('happy'); resetOffset(); showPose(0); });
controls.forEach(button => button.addEventListener('click', () => {
  const index = Number(button.dataset.pose);
  if (index === 5) pat(); else manualPose(index);
}));
pet.addEventListener('click', pat);
pet.addEventListener('keydown', event => {
  const index = {ArrowLeft:1, ArrowRight:2, ArrowUp:3, ArrowDown:4, Escape:0}[event.key];
  if (index === undefined) return;
  event.preventDefault(); manualPose(index);
});
reducedMotion.addEventListener('change', resetOffset);
const image = new Image();
image.onload = () => { pet.disabled = false; document.getElementById('loading').hidden = true; };
image.onerror = () => { document.getElementById('loading').textContent = '图片没有载入，请刷新预览页再试。'; };
image.src = './dog-poses.png';
