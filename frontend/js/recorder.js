// In-Browser Meeting Recorder Logic

let audioCtx = null;
let mediaRecorder = null;
let recordedChunks = [];
let screenStream = null;
let micStream = null;
let combinedStream = null;
let visualizerAnalyser = null;
let drawVisual = null;
let secondsRecorded = 0;
let timerInterval = null;
let recordedBlob = null;
let selectedSource = 'screen'; // default

// Web Speech API
let recognition = null;
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  
  recognition.onresult = (event) => {
    let interimTranscript = '';
    let finalTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      } else {
        interimTranscript += event.results[i][0].transcript;
      }
    }
    const box = document.getElementById('live-transcription-box');
    if (box) {
      box.textContent = finalTranscript || interimTranscript || "Listening...";
    }
  };
}

// Toast Helper
function showToast(message) {
  const toast = document.getElementById('toast');
  if (toast) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 4000);
  }
}

// Get selected source
function getSelectedSource() {
  return selectedSource;
}

// Populate Microphones list
async function loadMicrophones() {
  const select = document.getElementById('mic-select');
  if (!select) return;
  
  try {
    // Request permission to query devices
    await navigator.mediaDevices.getUserMedia({ audio: true });
    
    const devices = await navigator.mediaDevices.enumerateDevices();
    select.innerHTML = '';
    
    const audioDevices = devices.filter(d => d.kind === 'audioinput');
    audioDevices.forEach(device => {
      const option = document.createElement('option');
      option.value = device.deviceId;
      option.textContent = device.label || `Microphone ${select.length + 1}`;
      select.appendChild(option);
    });
  } catch (err) {
    console.error("Error loading microphones:", err);
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'Default Microphone';
    select.appendChild(option);
  }
}

// Handle source button click
document.querySelectorAll('.source-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.source-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedSource = btn.dataset.source;
  });
});

// Setup canvas visualizer
function setupVisualizer(stream) {
  const canvas = document.getElementById('canvas');
  if (!canvas) return;
  const canvasCtx = canvas.getContext('2d');
  
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  
  const sourceNode = audioCtx.createMediaStreamSource(stream);
  visualizerAnalyser = audioCtx.createAnalyser();
  visualizerAnalyser.fftSize = 256;
  sourceNode.connect(visualizerAnalyser);
  
  const bufferLength = visualizerAnalyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  
  function draw() {
    drawVisual = requestAnimationFrame(draw);
    visualizerAnalyser.getByteFrequencyData(dataArray);
    
    canvasCtx.fillStyle = 'rgba(8, 8, 16, 1)';
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
    
    const barWidth = (canvas.width / bufferLength) * 2.5;
    let barHeight;
    let x = 0;
    
    for (let i = 0; i < bufferLength; i++) {
      barHeight = dataArray[i] / 2;
      
      // Draw smooth wave colors
      canvasCtx.fillStyle = `rgb(${barHeight + 100}, 142, 247)`;
      canvasCtx.fillRect(x, canvas.height - barHeight, barWidth - 1, barHeight);
      
      x += barWidth + 1;
    }
  }
  
  draw();
}

// Timer helpers
function startTimer() {
  secondsRecorded = 0;
  const timerEl = document.getElementById('timer');
  timerInterval = setInterval(() => {
    secondsRecorded++;
    const mins = Math.floor(secondsRecorded / 60).toString().padStart(2, '0');
    const secs = (secondsRecorded % 60).toString().padStart(2, '0');
    timerEl.textContent = `${mins}:${secs}`;
  }, 1000);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

// Stop all media tracks
function stopTracks() {
  stopTimer();
  
  if (drawVisual) {
    cancelAnimationFrame(drawVisual);
    drawVisual = null;
  }
  
  if (screenStream) {
    screenStream.getTracks().forEach(t => t.stop());
    screenStream = null;
  }
  if (micStream) {
    micStream.getTracks().forEach(t => t.stop());
    micStream = null;
  }
  
  if (audioCtx && audioCtx.state !== 'closed') {
    audioCtx.close();
    audioCtx = null;
  }
  
  if (recognition) {
    try { recognition.stop(); } catch(e) {}
  }
}

// Setup start recording listener
document.getElementById('start-session-btn').addEventListener('click', async () => {
  recordedChunks = [];
  const source = getSelectedSource();
  const recordMic = document.getElementById('mic-toggle').checked;
  const recordSys = document.getElementById('system-audio-toggle').checked;
  const micId = document.getElementById('mic-select').value;
  
  try {
    let screenTracks = [];
    let systemAudioTracks = [];
    
    const displayConstraints = {
      video: {
        displaySurface: source === 'screen' ? 'monitor' : source
      },
      audio: recordSys
    };
    
    // Capture display
    screenStream = await navigator.mediaDevices.getDisplayMedia(displayConstraints);
    screenTracks = screenStream.getVideoTracks();
    systemAudioTracks = screenStream.getAudioTracks();
    
    let micTracks = [];
    if (recordMic) {
      try {
        micStream = await navigator.mediaDevices.getUserMedia({
          audio: micId ? { deviceId: { exact: micId } } : true
        });
        micTracks = micStream.getAudioTracks();
      } catch (micErr) {
        console.warn("Failed to get mic stream:", micErr);
        showToast("Warning: Microphone access denied. Capturing system audio only.");
      }
    }
    
    const audioTracksToMix = [...systemAudioTracks, ...micTracks];
    if (audioTracksToMix.length === 0) {
      throw new Error("No audio tracks captured. Enable mic or check display audio settings.");
    }
    
    if (audioTracksToMix.length > 1) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const dest = audioCtx.createMediaStreamDestination();
      
      audioTracksToMix.forEach(track => {
        const stream = new MediaStream([track]);
        const sourceNode = audioCtx.createMediaStreamSource(stream);
        sourceNode.connect(dest);
      });
      
      setupVisualizer(dest.stream);
      combinedStream = new MediaStream([
        ...screenTracks,
        ...dest.stream.getAudioTracks()
      ]);
    } else {
      const singleAudioStream = new MediaStream([audioTracksToMix[0]]);
      setupVisualizer(singleAudioStream);
      combinedStream = new MediaStream([
        ...screenTracks,
        audioTracksToMix[0]
      ]);
    }
    
    // Keep display stream alive for system audio but record only mixed audio to save space
    const audioOnlyStream = new MediaStream(combinedStream.getAudioTracks());
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
      ? 'audio/webm'
      : 'audio/ogg';

    console.log("Using mimeType:", mimeType);
    console.log("Stream obtained:", combinedStream.getTracks().map(t => t.kind));

    mediaRecorder = new MediaRecorder(audioOnlyStream, { mimeType });
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    };
    
    mediaRecorder.onstop = () => {
      // Assemble all chunks into one blob
      const blob = new Blob(recordedChunks, { type: mimeType });
      
      // Create object URL from blob
      const audioURL = URL.createObjectURL(blob);
      
      // Set on audio player
      const audioPlayer = document.getElementById('audio-player');
      if (audioPlayer) {
        audioPlayer.src = audioURL;
        audioPlayer.load();  // ← force reload the element
      }
      
      // Store blob for upload later
      window.recordedBlob = blob;
      
      console.log("Recording size:", blob.size, "bytes");
      console.log("Recording type:", blob.type);
      console.log("Chunks collected:", recordedChunks.length);
      console.log("Total size:", recordedChunks.reduce((a,b) => a + b.size, 0));
      
      stopTracks();
      prepareReview();
    };
    
    mediaRecorder.start(1000);
    startTimer();
    
    if (recognition) {
      try { recognition.start(); } catch(e) {}
    }
    
    document.getElementById('setup-pane').style.display = 'none';
    document.getElementById('recording-pane').style.display = 'block';
    showToast("Recording session active!");
    
  } catch (err) {
    console.error("Recording setup error:", err);
    showToast("Error initializing: " + err.message);
    stopTracks();
  }
});

// Pause / Resume recording
const pauseBtn = document.getElementById('pause-btn');
pauseBtn.addEventListener('click', () => {
  if (!mediaRecorder) return;
  
  if (mediaRecorder.state === 'recording') {
    mediaRecorder.pause();
    stopTimer();
    pauseBtn.textContent = 'Resume';
    document.getElementById('status-text').textContent = 'Paused';
    if (recognition) {
      try { recognition.stop(); } catch(e) {}
    }
  } else if (mediaRecorder.state === 'paused') {
    mediaRecorder.resume();
    // Resume timer count
    const timerEl = document.getElementById('timer');
    timerInterval = setInterval(() => {
      secondsRecorded++;
      const mins = Math.floor(secondsRecorded / 60).toString().padStart(2, '0');
      const secs = (secondsRecorded % 60).toString().padStart(2, '0');
      timerEl.textContent = `${mins}:${secs}`;
    }, 1000);
    
    pauseBtn.textContent = 'Pause';
    document.getElementById('status-text').textContent = 'Capturing...';
    if (recognition) {
      try { recognition.start(); } catch(e) {}
    }
  }
});

// Stop recording
document.getElementById('stop-btn').addEventListener('click', () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
});

// Prepare Review UI
function prepareReview() {
  recordedBlob = window.recordedBlob;
  const audioUrl = URL.createObjectURL(recordedBlob);
  
  const player = document.getElementById('audio-player');
  if (player) {
    player.src = audioUrl;
    player.load();
  }
  
  // Set default suggested title
  const dateStr = new Date().toISOString().split('T')[0];
  document.getElementById('meeting-title').value = `Meeting - ${dateStr}`;
  
  document.getElementById('recording-pane').style.display = 'none';
  document.getElementById('review-pane').style.display = 'block';
}

// Discard recording
document.getElementById('discard-btn').addEventListener('click', (e) => {
  e.preventDefault();
  if (confirm("Are you sure you want to discard this recording?")) {
    resetRecorder();
  }
});

function resetRecorder() {
  recordedChunks = [];
  recordedBlob = null;
  window.recordedBlob = null;
  document.getElementById('review-pane').style.display = 'none';
  document.getElementById('setup-pane').style.display = 'block';
  document.getElementById('timer').textContent = '00:00';
  document.getElementById('live-transcription-box').textContent = 'Speech-to-text preview will appear here as you speak...';
  document.getElementById('upload-progress-container').style.display = 'none';
  const player = document.getElementById('audio-player');
  if (player) player.src = '';
}

function showUploadProgress() {
  const uploadBtn = document.getElementById('upload-btn');
  if (uploadBtn) {
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';
  }
  const progressContainer = document.getElementById('upload-progress-container');
  if (progressContainer) {
    progressContainer.style.display = 'block';
  }
  const progressBar = document.getElementById('upload-progress-bar');
  if (progressBar) {
    progressBar.style.width = '100%';
  }
  const progressPercent = document.getElementById('upload-percent');
  if (progressPercent) {
    progressPercent.textContent = 'Processing...';
  }
}

function hideUploadProgress() {
  const uploadBtn = document.getElementById('upload-btn');
  if (uploadBtn) {
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Process with AI';
  }
  const progressContainer = document.getElementById('upload-progress-container');
  if (progressContainer) {
    progressContainer.style.display = 'none';
  }
}

async function uploadRecording() {
  const blob = window.recordedBlob;
  
  if (!blob || blob.size === 0) {
    showToast("No recording found. Please record again.");
    return;
  }
  
  // Get auth token - check both storage locations
  const token = localStorage.getItem("meetmind_token") 
    || localStorage.getItem("token")
    || localStorage.getItem("access_token")
    || getCookie("token");
  
  console.log("Token found:", token ? "YES" : "NO");
  
  if (!token) {
    showToast("Session expired. Please login again.");
    window.location.href = "/login.html";
    return;
  }
  
  // Get title and language
  const title = document.getElementById('meeting-title').value 
    || "Meeting - " + new Date().toLocaleDateString();
  const language = document.getElementById('language-select').value || "auto";
  
  // Build form data
  const formData = new FormData();
  
  // Add file with correct extension based on mimeType
  const extension = blob.type.includes('ogg') ? 'ogg' : 'webm';
  formData.append('file', blob, `recording.${extension}`);
  formData.append('title', title);
  formData.append('language', language);
  
  const uploadUrl = (typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : "https://meetmind-backend-90u7.onrender.com") + "/api/v1/meetings/upload";
  console.log("Uploading:", blob.size, "bytes as recording." + extension);
  console.log("To:", uploadUrl);
  
  // Show progress UI
  showUploadProgress();
  
  try {
    const response = await fetch(
      uploadUrl,
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
          // DO NOT set Content-Type here — browser sets it automatically
          // with correct boundary for multipart/form-data
        },
        body: formData
      }
    );
    
    console.log("Upload response status:", response.status);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error("Upload error:", errorData);
      
      if (response.status === 401) {
        showToast("Session expired. Please login again.");
        window.location.href = "/login.html";
        return;
      }
      
      throw new Error(errorData.detail || "Upload failed");
    }
    
    const data = await response.json();
    console.log("Upload success:", data);
    
    // Redirect to meeting page
    window.location.href = `/meeting.html?id=${data.meeting_id || data.id}`;
    
  } catch (error) {
    console.error("Upload failed:", error);
    showToast("Upload failed: " + error.message);
    hideUploadProgress();
  }
}

// Upload & Process recording
const uploadBtn = document.getElementById('upload-btn');
if (uploadBtn) {
  uploadBtn.addEventListener('click', uploadRecording);
}

// Request permission for browser notifications on load
if ("Notification" in window && Notification.permission === "default") {
  Notification.requestPermission();
}

// Load Microphones list on startup
loadMicrophones();

// Debug logs on load
console.log("Recorder page loaded");
console.log("Auth token:", localStorage.getItem("meetmind_token") ? "found" : "missing");
