import { initializeApp } from 'firebase/app';
import { getFirestore, collection, addDoc, onSnapshot, query, where, orderBy, limit, serverTimestamp, doc } from 'firebase/firestore';

const firebaseConfig = {
    apiKey: "AIzaSyDxwNlMl2YE1-7165UAx4NK6GfhuowpibY",
    authDomain: "pitch-promo-xyz-0727.firebaseapp.com",
    projectId: "pitch-promo-xyz-0727",
    storageBucket: "pitch-promo-xyz-0727.firebasestorage.app",
    messagingSenderId: "659061058166",
    appId: "1:659061058166:web:13863ac4b6dd5125f34d57"
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

export { db, collection, addDoc, onSnapshot, query, where, orderBy, limit, serverTimestamp, doc };
