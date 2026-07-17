// src/firebase.js
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyBMIRJ6S2necnXjoY_l_TRET0nyrNNwUyI",
  authDomain: "radarix-f758f.firebaseapp.com",
  projectId: "radarix-f758f",
  storageBucket: "radarix-f758f.appspot.com",
  messagingSenderId: "259618726786",
  appId: "1:259618726786:web:6e6bb96a2be1f53148a59b"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firebase Authentication
export const auth = getAuth(app);   

// Initialize Firestore (optional)
export const db = getFirestore(app);
