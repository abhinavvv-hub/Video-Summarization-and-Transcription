const uploadArea = document.getElementById('uploadArea');
const videoInput = document.getElementById('videoInput');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const removeFile = document.getElementById('removeFile');
const processBtn = document.getElementById('processBtn');
const uploadSection = document.getElementById('uploadSection');
const progressSection = document.getElementById('progressSection');
const progressText = document.getElementById('progressText');
const resultsSection = document.getElementById('resultsSection');
const resetBtn = document.getElementById('resetBtn');

let selectedFile = null;

uploadArea.addEventListener('click', () => {
    videoInput.click();
});

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

videoInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
});

function handleFile(file) {
    selectedFile = file;
    fileName.textContent = file.name;
    fileInfo.style.display = 'flex';
    uploadArea.style.display = 'none';
    processBtn.disabled = false;
}

removeFile.addEventListener('click', () => {
    selectedFile = null;
    videoInput.value = '';
    fileInfo.style.display = 'none';
    uploadArea.style.display = 'block';
    processBtn.disabled = true;
});

processBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    
    console.log('Processing file:', selectedFile.name);
    
    uploadSection.style.display = 'none';
    progressSection.style.display = 'block';
    resultsSection.style.display = 'none';
    
    progressText.textContent = 'Uploading and transcribing video...';
    
    const formData = new FormData();
    formData.append('video', selectedFile);
    
    const btnText = processBtn.querySelector('.btn-text');
    const spinner = processBtn.querySelector('.loading-spinner');
    btnText.textContent = 'Processing...';
    spinner.style.display = 'inline-block';
    
    try {
        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Processing failed');
        }
        
        progressText.textContent = 'Generating summary...';
        
        displayResults(data);
        
    } catch (error) {
        console.error('Error:', error);
        alert('Error: ' + error.message);
        uploadSection.style.display = 'block';
        progressSection.style.display = 'none';
    } finally {
        btnText.textContent = 'Process Video';
        spinner.style.display = 'none';
        processBtn.disabled = false;
    }
});

function displayResults(data) {
    progressSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    const summary = data.summary;
    
    const overviewContent = document.getElementById('overviewContent');
    overviewContent.textContent = summary.overview || 'No overview available';
    overviewContent.classList.add('loading');
    setTimeout(() => overviewContent.classList.remove('loading'), 500);
    
    const takeawaysList = document.getElementById('takeawaysContent');
    takeawaysList.innerHTML = '';
    if (summary.key_takeaways && summary.key_takeaways.length > 0) {
        summary.key_takeaways.forEach(takeaway => {
            const li = document.createElement('li');
            li.textContent = takeaway;
            takeawaysList.appendChild(li);
        });
    } else {
        takeawaysList.innerHTML = '<li>No takeaways available</li>';
    }
    
    const pointsContent = document.getElementById('pointsContent');
    pointsContent.innerHTML = '';
    if (summary.important_points && summary.important_points.length > 0) {
        summary.important_points.forEach(point => {
            const div = document.createElement('div');
            div.className = 'point-item';
            if (point.details) {
                div.innerHTML = `<strong>${point.topic}:</strong> ${point.details}`;
            } else {
                div.innerHTML = `<strong>${point.topic}</strong>`;
            }
            pointsContent.appendChild(div);
        });
    } else {
        pointsContent.textContent = 'No important points available';
    }
    
    const adviceList = document.getElementById('adviceContent');
    adviceList.innerHTML = '';
    if (summary.actionable_advice && summary.actionable_advice.length > 0) {
        summary.actionable_advice.forEach(advice => {
            const li = document.createElement('li');
            li.textContent = advice;
            adviceList.appendChild(li);
        });
    } else {
        adviceList.innerHTML = '<li>No advice available</li>';
    }
    
    const summaryContent = document.getElementById('summaryContent');
    summaryContent.textContent = summary.final_summary || 'No summary available';
    
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

resetBtn.addEventListener('click', () => {
    selectedFile = null;
    videoInput.value = '';
    fileInfo.style.display = 'none';
    uploadArea.style.display = 'block';
    processBtn.disabled = true;
    resultsSection.style.display = 'none';
    uploadSection.style.display = 'block';
    uploadSection.scrollIntoView({ behavior: 'smooth' });
});
