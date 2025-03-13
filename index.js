// ตัวอย่างโค้ด JavaScript สำหรับ LIFF App
// ไฟล์: index.js

// Import LIFF SDK
import liff from '@line/liff';

// ฟังก์ชันเริ่มต้น LIFF
async function initializeLiff(myLiffId) {
  try {
    // เริ่มต้น LIFF
    await liff.init({
      liffId: myLiffId
    });
    
    // ตรวจสอบว่าผู้ใช้เข้าสู่ระบบหรือไม่
    if (!liff.isLoggedIn()) {
      // ถ้ายังไม่ได้เข้าสู่ระบบ ให้ล็อกอิน
      liff.login();
    } else {
      // ถ้าเข้าสู่ระบบแล้ว ดำเนินการต่อ
      getUserProfile();
    }
  } catch (error) {
    console.error('LIFF initialization failed', error);
    document.getElementById('liffAppContent').innerHTML = 
      `<p>Something went wrong with LIFF initialization: ${error}</p>`;
  }
}

// ฟังก์ชันดึงข้อมูลโปรไฟล์ผู้ใช้
async function getUserProfile() {
  try {
    // ดึงข้อมูลโปรไฟล์
    const profile = await liff.getProfile();
    
    // แสดงผลข้อมูล
    document.getElementById('userIdProfileField').textContent = profile.userId;
    document.getElementById('displayNameField').textContent = profile.displayName;
    
    // แสดงรูปโปรไฟล์
    if (profile.pictureUrl) {
      document.getElementById('profilePictureDiv').style.display = "block";
      document.getElementById('profilePictureImage').src = profile.pictureUrl;
    }
    
    // แสดง email (ถ้าได้รับอนุญาต)
    if (liff.getDecodedIDToken().email) {
      document.getElementById('emailField').textContent = liff.getDecodedIDToken().email;
    }
    
    // แสดงส่วนของเนื้อหา
    document.getElementById('liffInitErrorMessage').style.display = "none";
    document.getElementById('liffAppContent').style.display = "block";
    
  } catch (error) {
    console.error('Error getting profile', error);
  }
}

// ฟังก์ชันส่งข้อความ
function sendMessage() {
  if (!liff.isInClient()) {
    alert('This button is only available in the LINE app');
    return;
  }
  
  liff.sendMessages([
    {
      type: 'text',
      text: document.getElementById('messageText').value
    }
  ])
  .then(() => {
    alert('Message sent');
  })
  .catch((error) => {
    console.error('Error sending message', error);
  });
}

// ฟังก์ชันปิด LIFF App
function closeLiff() {
  if (!liff.isInClient()) {
    alert('This button is only available in the LINE app');
    return;
  }
  
  liff.closeWindow();
}

// เมื่อหน้าเว็บโหลดเสร็จ
window.onload = function() {
  // ตรวจสอบว่าเป็นการเปิดจากในแอพ LINE หรือเบราว์เซอร์
  const useNodeJS = false;
  let myLiffId = "";
  
  if (useNodeJS) {
    // ถ้าใช้ Node.js เซิร์ฟเวอร์ จะดึง LIFF ID จาก environment variable
    fetch('/send-id')
      .then(function(reqResponse) {
        return reqResponse.json();
      })
      .then(function(jsonResponse) {
        myLiffId = jsonResponse.id;
        initializeLiff(myLiffId);
      })
      .catch(function(error) {
        console.error('Error getting LIFF ID', error);
      });
  } else {
    // ถ้าไม่ได้ใช้ Node.js ให้กำหนด LIFF ID ตรงนี้
    myLiffId = "2007057489-peM79G6w"; // แทนที่ด้วย LIFF ID ของคุณ
    initializeLiff(myLiffId);
  }
  
  // ผูกอีเวนต์กับปุ่ม
  document.getElementById('sendMessageButton').onclick = sendMessage;
  document.getElementById('closeButton').onclick = closeLiff;
};
