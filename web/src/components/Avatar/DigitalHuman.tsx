'use client';

import React, { useEffect, useState } from 'react';
import { useLoader, useFrame } from '@react-three/fiber';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { avatarController } from './controllers/AvatarController';
import { useEyeTracking } from './hooks/useEyeTracking';
import { useAvatarAnimation } from './hooks/useAvatarAnimation';
import { useLipSync } from './hooks/useLipSync';
import { useEmotionEngine } from './hooks/useEmotionEngine';
import { useNavigation } from './hooks/useNavigation';

export function DigitalHuman() {
  const [vrmModel, setVrmModel] = useState<any>(null);
  const [modelUrl, setModelUrl] = useState(avatarController.modelUrl);

  // Listen for model switches from controller
  useEffect(() => {
    const unsubscribe = avatarController.subscribe((ctrl) => {
      if (ctrl.modelUrl !== modelUrl) {
        setModelUrl(ctrl.modelUrl);
      }
    });
    return unsubscribe;
  }, [modelUrl]);

  // Load GLTF with VRMLoaderPlugin
  const gltf = useLoader(GLTFLoader, modelUrl, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  });

  useEffect(() => {
    if (gltf) {
      const vrm = (gltf.userData as any).vrm;

      if (vrm) {
        // Optimize VRM: rotate Y by 180 degrees because VRM models look towards +Z by default
        vrm.scene.rotation.y = Math.PI;
        
        // Enlarge the companion model for the main holographic workspace.
        // Keep the root position controlled by useNavigation; scale only the model geometry.
        vrm.scene.scale.setScalar(2.6);

        // Setup materials and render settings
        vrm.scene.traverse((obj: any) => {
          if (obj.isMesh) {
            obj.castShadow = true;
            obj.receiveShadow = false;
            
            // VRM meshes usually have custom material properties.
            // Let's ensure smooth material lighting.
            if (obj.material) {
              obj.material.roughness = 0.65;
              obj.material.metalness = 0.1;
            }
          }
        });

        // Remove unused/unnormalized objects
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.removeUnnecessaryJoints(gltf.scene);

        setVrmModel(vrm);
        
        // Register VRM inside our global Controller
        avatarController.register(vrm, null, {});
      }
    }

    return () => {
      avatarController.unregister();
    };
  }, [gltf]);

  // Bind core character animation/simulation hooks
  useEyeTracking(vrmModel);
  useAvatarAnimation(vrmModel);
  useLipSync(vrmModel);
  useEmotionEngine(vrmModel);
  useNavigation(vrmModel);

  // Run the VRM update loop on every frame (handles spring bone physics)
  useFrame((state, delta) => {
    if (vrmModel) {
      vrmModel.update(delta);
    }
  });

  if (!vrmModel) return null;

  return (
    <primitive object={vrmModel.scene} />
  );
}
