// add this line for OrbitControls:
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js';
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';


const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, window.innerWidth/window.innerHeight, 0.1, 1000);
camera.position.set(0, 20, 50);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// set up OrbitControls so you can pan/zoom/rotate with mouse
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;      // an animation loop is required
controls.dampingFactor = 0.05;
controls.screenSpacePanning = false;
controls.minDistance = 10;
controls.maxDistance = 200;

// Lighting
const light = new THREE.DirectionalLight(0xffffff, 1);
light.position.set(50, 100, 50);
scene.add(light);

// Ground grid
const grid = new THREE.GridHelper(200, 20);
scene.add(grid);

// Example tiles
const visibleTiles = ['tile_15_12', 'tile_15_13']; // Replace with dynamic list

function createTileMesh(id, index) {
  const geometry = new THREE.BoxGeometry(10, 1, 10);
  const material = new THREE.MeshStandardMaterial({ color: 0x0077ff });
  const mesh = new THREE.Mesh(geometry, material);

  mesh.position.x = (index % 10) * 12;
  mesh.position.z = Math.floor(index / 10) * 12;
  mesh.name = id;

  return mesh;
}

visibleTiles.forEach((id, i) => {
  const tile = createTileMesh(id, i);
  scene.add(tile);
});

// Animation loop
function animate() {
  requestAnimationFrame(animate);
  controls.update();               // required if enableDamping = true
  renderer.render(scene, camera);
}
animate();
