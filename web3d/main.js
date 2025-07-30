/* main.js: Full example showing filtered loading of real 3D Tiles */

import * as THREE        from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js';
import { loadTiles, tilesInView } from './tiles-utils.js';
import { Loader3DTiles } from 'three-loader-3dtiles';


// Scene & camera setup
const scene  = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(
  60,
  window.innerWidth / window.innerHeight,
  0.1,
   1e7  //
);


// Renderer
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// OrbitControls for interaction
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.minDistance = 10;
controls.maxDistance = 200;

// Lighting + grid helper
const light = new THREE.DirectionalLight(0xffffff, 1);
light.position.set(50, 100, 50);
scene.add(light);
scene.add(new THREE.GridHelper(200, 20));

// Track loaded runtimes if needed
const runtimes = [];



camera.position.set(
  -3048634.534137 + 100, // Offset for visibility
  4046527.673589 + 100,
  3876522.228654 + 100
);
camera.lookAt(
  -3048634.534137,
  4046527.673589,
  3876522.228654
);



async function initTiles() {
  try {
    // 1) Load tileset metadata
    const tiles = await loadTiles('/setagaya_no_texture/tileset.json');

    // 2) Compute visible URIs
    const camLat = 35.65293345953977;
    const camLon = 139.6139378111143;
    const lookLat = 35.6527645;
    const lookLon = 139.6139331;
    const visibleUris = tilesInView(
      tiles,
      camLat, camLon,
      lookLat, lookLon,
      60,    // FOV
      500  // max distance
    );
    console.log('Visible tile URIs:', visibleUris);
    await loadTileset()
 
  } catch (err) {
    console.error('initTiles error:', err);
  }
}
let tilesRuntime = null;

async function loadTileset() {
  const { model, runtime } = await Loader3DTiles.load({
    url:'/setagaya_no_texture/tileset.json',
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
      devicePixelRatio: window.devicePixelRatio
    },
    options: {
      // Note the trailing slashes—these folders host the .js/.wasm decoder files
      dracoDecoderPath: 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/libs/draco/',
      basisTranscoderPath: 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/libs/basis/',
          maximumScreenSpaceError: 10000,
    loadSiblings: true,
    skipLOD: false


      
    }
  });

  // Keep the runtime if you need to update per‑frame
  tilesRuntime = runtime;

  runtimes.push(runtime);
  scene.add(model);
  console.log('Tileset model:', model);
console.log('Runtime:', runtime);


}

initTiles();


// Render loop
function animate() {
  requestAnimationFrame(animate);
  

  // If runtimes have update method, call refine or update
  for (const rt of runtimes) {
    if (typeof rt.update === 'function') {
        rt.update(camera);  // Pass the camera!s
    }
  }
  

  controls.update();
  
  renderer.render(scene, camera);
}
animate();

