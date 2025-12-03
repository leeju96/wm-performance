importScripts("https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/9.23.0/firebase-messaging-compat.js");

firebase.initializeApp({
  apiKey: "AIzaSyBy_EMdPVGh2u4UEXlro90TZcCl_mfTg_s",
  authDomain: "wm-performance.firebaseapp.com",
  projectId: "wm-performance",
  storageBucket: "wm-performance.firebasestorage.app",
  messagingSenderId: "802188460964",
  appId: "1:802188460964:web:2f464c2ea4eed83ab93731"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  self.registration.showNotification(payload.notification.title, {
    body: payload.notification.body,
    icon: "/static/icon192.png",
  });
});
