@app.route('/')
def dashboard():
    """Serve the dashboard HTML"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMS Management Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        h2 {
            color: #555;
            margin-top: 20px;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"], input[type="url"], textarea, input[type="file"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin-right: 10px;
            margin-bottom: 10px;
        }
        button:hover {
            background-color: #0056b3;
        }
        .danger-button {
            background-color: #dc3545;
        }
        .danger-button:hover {
            background-color: #c82333;
        }
        .section {
            border-bottom: 1px solid #eee;
            padding-bottom: 20px;
            margin-bottom: 20px;
        }
        .section:last-child {
            border-bottom: none;
        }
        #status {
            padding: 10px;
            margin-top: 10px;
            border-radius: 5px;
            display: none;
        }
        .success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .form-row {
            display: flex;
            gap: 10px;
        }
        .form-row input {
            flex: 1;
        }
        .checkbox-group {
            margin: 10px 0;
        }
        .checkbox-group label {
            display: inline;
            font-weight: normal;
            margin-left: 5px;
        }
        .preview-area {
            margin-top: 20px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background-color: #f8f9fa;
            max-height: 300px;
            overflow-y: auto;
            display: none;
        }
        .preview-header {
            font-weight: bold;
            margin-bottom: 10px;
        }
        .preview-list {
            margin: 0;
            padding-left: 20px;
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
            border-bottom: 1px solid #ddd;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            margin-right: 5px;
            border: 1px solid #ddd;
            border-bottom: none;
            border-radius: 5px 5px 0 0;
            background-color: #f8f9fa;
        }
        .tab.active {
            background-color: white;
            border-bottom: 1px solid white;
            margin-bottom: -1px;
            font-weight: bold;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .column-selector {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 15px;
        }
        .column-item {
            background-color: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 10px;
            cursor: pointer;
        }
        .column-item.selected {
            background-color: #d1ecf1;
            border-color: #bee5eb;
        }
        .column-preview-table {
            width: 100%;
            overflow-x: auto;
            margin-top: 20px;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            max-width: 80%;
            max-height: 80%;
            overflow-y: auto;
        }
        .close-button {
            float: right;
            cursor: pointer;
            background: none;
            border: none;
            font-size: 20px;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 SMS Management Dashboard</h1>
        
        <div class="tabs">
            <div class="tab active" onclick="openTab(event, 'tab-single')">Single Number</div>
            <div class="tab" onclick="openTab(event, 'tab-csv')">CSV Upload</div>
            <div class="tab" onclick="openTab(event, 'tab-survey')">Send Survey</div>
            <div class="tab" onclick="openTab(event, 'tab-manage')">Manage Data</div>
            <div class="tab" onclick="openTab(event, 'tab-columns')">Manage Columns</div>
            <div class="tab" onclick="openTab(event, 'tab-data')">View Data</div>
        </div>
        
        <div id="tab-single" class="tab-content active">
            <div class="section">
                <h2>Send Consent Request to Single Number</h2>
                <div class="form-group">
                    <label for="phone">Phone Number (e.g., +16478941552):</label>
                    <input type="text" id="phone" placeholder="+1234567890">
                </div>
                <button onclick="sendConsent()">Send Consent Request</button>
            </div>
        </div>
        
        <div id="tab-csv" class="tab-content">
            <div class="section">
                <h2>Upload CSV with Phone Numbers</h2>
                <div class="form-group">
                    <label for="csvFile">Select a CSV file with phone numbers:</label>
                    <input type="file" id="csvFile" accept=".csv">
                    <p style="color: #6c757d; font-size: 14px; margin-top: 5px;">
                        Upload a CSV file to extract phone numbers and additional data.
                        You'll be able to select which columns to import after upload.
                    </p>
                </div>
                <button onclick="uploadCSV()">Upload CSV</button>
                
                <div id="columnSelectionArea" class="preview-area">
                    <div class="preview-header">Column Selection</div>
                    <p>Please select which columns you want to import from the CSV file:</p>
                    
                    <div class="form-group">
                        <label for="phoneColumnSelect">Phone Number Column:</label>
                        <select id="phoneColumnSelect"></select>
                    </div>
                    
                    <div id="columnSelector" class="column-selector">
                        <!-- Column options will be added here -->
                    </div>
                    
                    <div class="column-preview-table">
                        <h3>Data Preview</h3>
                        <div style="overflow-x: auto;">
                            <table id="previewTable">
                                <thead>
                                    <tr id="previewTableHeader">
                                        <!-- Headers will be added here -->
                                    </tr>
                                </thead>
                                <tbody id="previewTableBody">
                                    <!-- Preview data will be added here -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <div class="checkbox-group" style="margin-top: 15px;">
                        <input type="checkbox" id="sendConsentAfterImport">
                        <label for="sendConsentAfterImport">Send consent requests immediately after import</label>
                    </div>
                    
                    <button onclick="processSelectedColumns()" style="margin-top: 15px;">Import Selected Columns</button>
                </div>
            </div>
        </div>
        
        <div id="tab-survey" class="tab-content">
            <div class="section">
                <h2>Send Survey Link</h2>
                <div class="form-group">
                    <label for="surveyUrl">Survey URL:</label>
                    <input type="url" id="surveyUrl" placeholder="https://your-survey-link.com">
                </div>
                <div class="form-group">
                    <label for="customMessage">Custom Message (optional):</label>
                    <textarea id="customMessage" rows="3" placeholder="Enter a custom message to send with the survey link..."></textarea>
                </div>
                <button onclick="sendSurvey()">Send Survey to All Consented Participants</button>
            </div>
        </div>
        
        <div id="tab-manage" class="tab-content">
            <div class="section">
                <h2>Manage Participants</h2>
                <div style="margin-bottom: 15px;">
                    <button onclick="viewParticipants()">View All Participants</button>
                    <button onclick="exportData()">Export Data to CSV</button>
                </div>
                <div id="participantsTable" style="margin-top: 20px; display: none;">
                    <table id="participantsData" style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th style="border: 1px solid #ddd; padding: 8px;">Phone Number</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">Consent Status</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">Email</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">Survey Sent</th>
                                <th style="border: 1px solid #ddd; padding: 8px;">Additional Data</th>
                            </tr>
                        </thead>
                        <tbody id="participantsBody">
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="section">
                <h2>Database Management</h2>
                <p style="color: #6c757d; font-size: 14px;">⚠️ Danger Zone: These actions cannot be undone!</p>
                <button class="danger-button" onclick="clearDatabase()">Clear All Data</button>
                <button onclick="resetSurveySent()">Reset Survey Sent Status</button>
            </div>
            
            <div class="section">
                <h2>App Status</h2>
                <button onclick="checkHealth()">Check App Health</button>
                <div id="healthInfo" style="margin-top: 10px; display: none;">
                    <div id="healthStatus"></div>
                </div>
            </div>
        </div>
        
        <div id="tab-columns" class="tab-content">
            <div class="section">
                <h2>Manage CSV Columns</h2>
                <p>Add custom columns or manage existing ones that will be used when importing CSV data.</p>
                
                <div class="form-group">
                    <h3>Add New Column</h3>
                    <div class="form-row">
                        <div style="flex: 2;">
                            <label for="newColumnName">Column Name (Database ID):</label>
                            <input type="text" id="newColumnName" placeholder="e.g., last_fed_vote_intent">
                        </div>
                        <div style="flex: 2;">
                            <label for="newDisplayName">Display Name:</label>
                            <input type="text" id="newDisplayName" placeholder="e.g., Last Federal Vote Intent">
                        </div>
                        <div>
                            <label for="newDataType">Data Type:</label>
                            <select id="newDataType">
                                <option value="TEXT">Text</option>
                                <option value="INTEGER">Integer</option>
                                <option value="REAL">Decimal</option>
                                <option value="DATE">Date</option>
                            </select>
                        </div>
                    </div>
                    <button onclick="addNewColumn()" style="margin-top: 10px;">Add Column</button>
                </div>
                
                <div class="form-group" style="margin-top: 20px;">
                    <h3>Existing Columns</h3>
                    <button onclick="loadColumnDefinitions()">Load Columns</button>
                    <div id="columnsTable" style="margin-top: 15px; display: none;">
                        <table id="columnDefinitionsTable" style="width: 100%;">
                            <thead>
                                <tr>
                                    <th>Column Name</th>
                                    <th>Display Name</th>
                                    <th>Data Type</th>
                                    <th>Active</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="columnDefinitionsBody">
                                <!-- Column definitions will be added here -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="tab-data" class="tab-content">
            <div class="section">
                <h2>View Detailed Participant Data</h2>
                <p>This tab shows all participant data including the additional fields imported from CSV files.</p>
                <button onclick="viewDetailedData()">Load Detailed Data</button>
                <div id="detailedDataTable" style="margin-top: 20px; display: none; overflow-x: auto;">
                    <table id="fullDataTable" style="width: 100%; border-collapse: collapse;">
                        <thead id="fullDataHeader">
                            <!-- Headers will be dynamically generated -->
                        </thead>
                        <tbody id="fullDataBody">
                            <!-- Data will be dynamically generated -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div id="status"></div>
    </div>
    
    <!-- Modal for CSV Column Selection -->
    <div id="columnSelectionModal" class="modal">
        <div class="modal-content">
            <button class="close-button" onclick="closeModal('columnSelectionModal')">&times;</button>
            <h2>Select Columns to Import</h2>
            <div id="modalColumnSelector"></div>
            <button onclick="confirmColumnSelection()">Confirm Selection</button>
        </div>
    </div>

    <script>
        const API_BASE = window.location.origin;
        let extractedPhoneNumbers = [];
        let csvHeaders = [];
        let csvPhoneColumn = '';
        let csvPreviewData = [];
        let csvSessionId = '';
        let selectedColumns = [];

        function openTab(evt, tabName) {
            // Hide all tab content
            const tabContents = document.getElementsByClassName("tab-content");
            for (let i = 0; i < tabContents.length; i++) {
                tabContents[i].classList.remove("active");
            }
            
            // Remove active class from all tabs
            const tabs = document.getElementsByClassName("tab");
            for (let i = 0; i < tabs.length; i++) {
                tabs[i].classList.remove("active");
            }
            
            // Show the selected tab content and add active class to the tab
            document.getElementById(tabName).classList.add("active");
            evt.currentTarget.classList.add("active");
        }

        function showStatus(message, isSuccess = true) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = isSuccess ? 'success' : 'error';
            status.style.display = 'block';
            setTimeout(() => {
                status.style.display = 'none';
            }, 5000);
        }

        function openModal(modalId) {
            document.getElementById(modalId).style.display = 'flex';
        }

        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }

        async function sendConsent() {
            const phone = document.getElementById('phone').value;
            if (!phone) {
                showStatus('Please enter a phone number', false);
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/send_consent`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `phone_number=${encodeURIComponent(phone)}`
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
            } catch (error) {
                showStatus('Error sending consent request: ' + error.message, false);
            }
        }

        async function uploadCSV() {
            const fileInput = document.getElementById('csvFile');
            
            if (!fileInput.files || fileInput.files.length === 0) {
                showStatus('Please select a CSV file', false);
                return;
            }

            const file = fileInput.files[0];
            if (!file.name.endsWith('.csv')) {
                showStatus('Please select a CSV file', false);
                return;
            }

            const formData = new FormData();
            formData.append('file', file);

            try {
                showStatus('Uploading and analyzing CSV...', true);
                
                const response = await fetch(`${API_BASE}/upload_csv`, {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    // Store CSV information
                    csvHeaders = result.headers;
                    csvPhoneColumn = result.phone_column;
                    csvPreviewData = result.preview_data;
                    csvSessionId = result.session_id;
                    
                    // Show column selection interface
                    displayColumnSelection();
                    
                    showStatus(`CSV uploaded successfully. Please select columns to import.`, true);
                } else {
                    showStatus(result.message || 'Error processing CSV file', false);
                }
            } catch (error) {
                showStatus('Error uploading CSV: ' + error.message, false);
            }
        }
        
        function displayColumnSelection() {
            // Clear previous data
            selectedColumns = [];
            
            // Populate phone column dropdown
            const phoneColumnSelect = document.getElementById('phoneColumnSelect');
            phoneColumnSelect.innerHTML = '';
            
            csvHeaders.forEach(header => {
                const option = document.createElement('option');
                option.value = header;
                option.textContent = header;
                phoneColumnSelect.appendChild(option);
                
                // Select the automatically detected phone column
                if (header === csvPhoneColumn) {
                    option.selected = true;
                }
            });
            
            // Populate column selector
            const columnSelector = document.getElementById('columnSelector');
            columnSelector.innerHTML = '';
            
            csvHeaders.forEach(header => {
                if (header !== csvPhoneColumn) {
                    const columnItem = document.createElement('div');
                    columnItem.className = 'column-item';
                    columnItem.setAttribute('data-column', header);
                    columnItem.textContent = header;
                    columnItem.onclick = function() {
                        this.classList.toggle('selected');
                        
                        // Update selected columns list
                        const column = this.getAttribute('data-column');
                        if (this.classList.contains('selected')) {
                            if (!selectedColumns.includes(column)) {
                                selectedColumns.push(column);
                            }
                        } else {
                            const index = selectedColumns.indexOf(column);
                            if (index !== -1) {
                                selectedColumns.splice(index, 1);
                            }
                        }
                    };
                    columnSelector.appendChild(columnItem);
                }
            });
            
            // Populate data preview table
            const previewTableHeader = document.getElementById('previewTableHeader');
            previewTableHeader.innerHTML = '';
            
            // Add header cells
            csvHeaders.forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                previewTableHeader.appendChild(th);
            });
            
            // Add data rows
            const previewTableBody = document.getElementById('previewTableBody');
            previewTableBody.innerHTML = '';
            
            csvPreviewData.forEach(rowData => {
                const tr = document.createElement('tr');
                
                csvHeaders.forEach(header => {
                    const td = document.createElement('td');
                    td.textContent = rowData[header] || '';
                    tr.appendChild(td);
                });
                
                previewTableBody.appendChild(tr);
            });
            
            // Show the column selection area
            document.getElementById('columnSelectionArea').style.display = 'block';
        }
        
        async function processSelectedColumns() {
            const phoneColumn = document.getElementById('phoneColumnSelect').value;
            const sendConsent = document.getElementById('sendConsentAfterImport').checked;
            
            if (selectedColumns.length === 0) {
                if (!confirm('You haven\'t selected any columns to import besides the phone number. Continue with just phone numbers?')) {
                    return;
                }
            }
            
            // Add phone column to selected columns
            if (!selectedColumns.includes(phoneColumn)) {
                selectedColumns.push(phoneColumn);
            }
            
            try {
                showStatus('Processing selected columns...', true);
                
                const response = await fetch(`${API_BASE}/process_selected_columns`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        session_id: csvSessionId,
                        phone_column: phoneColumn,
                        selected_columns: selectedColumns,
                        send_consent: sendConsent
                    })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    if (sendConsent) {
                        showStatus(`Successfully imported data and sent consent requests to ${result.successful_sends} out of ${result.total} participants`, true);
                    } else {
                        showStatus(`Successfully imported data for ${result.total} participants`, true);
                    }
                    
                    // Hide column selection area and reset file input
                    document.getElementById('columnSelectionArea').style.display = 'none';
                    document.getElementById('csvFile').value = '';
                } else {
                    showStatus(result.message || 'Error processing columns', false);
                }
            } catch (error) {
                showStatus('Error processing columns: ' + error.message, false);
            }
        }

        async function sendSurvey() {
            const surveyUrl = document.getElementById('surveyUrl').value;
            const customMessage = document.getElementById('customMessage').value;
            
            if (!surveyUrl) {
                showStatus('Please enter a survey URL', false);
                return;
            }

            try {
                const body = `survey_url=${encodeURIComponent(surveyUrl)}`;
                const fullBody = customMessage ? 
                    `${body}&custom_message=${encodeURIComponent(customMessage)}` : body;
                
                const response = await fetch(`${API_BASE}/send_survey`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: fullBody
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
            } catch (error) {
                showStatus('Error sending survey: ' + error.message, false);
            }
        }

        async function viewParticipants() {
            try {
                const response = await fetch(`${API_BASE}/participants`);
                const result = await response.json();
                
                if (result.status === 'success') {
                    const tbody = document.getElementById('participantsBody');
                    tbody.innerHTML = '';
                    
                    if (result.data && result.data.length > 0) {
                        result.data.forEach(participant => {
                            const row = tbody.insertRow();
                            row.insertCell(0).textContent = participant.phone_number;
                            row.insertCell(1).textContent = participant.consent_status;
                            row.insertCell(2).textContent = participant.email || 'N/A';
                            row.insertCell(3).textContent = participant.survey_sent ? 'Yes' : 'No';
                            
                            // Add button to view additional data
                            const additionalCell = row.insertCell(4);
                            const viewButton = document.createElement('button');
                            viewButton.textContent = 'View Data';
                            viewButton.style.padding = '5px 10px';
                            viewButton.style.fontSize = '12px';
                            viewButton.onclick = () => showAdditionalData(participant);
                            additionalCell.appendChild(viewButton);
                        });
                    } else {
                        const row = tbody.insertRow();
                        const cell = row.insertCell(0);
                        cell.colSpan = 5;
                        cell.textContent = 'No participants found';
                        cell.style.textAlign = 'center';
                    }
                    
                    document.getElementById('participantsTable').style.display = 'block';
                    showStatus('Participants loaded successfully', true);
                } else {
                    showStatus('Error loading participants', false);
                }
            } catch (error) {
                showStatus('Error fetching participants: ' + error.message, false);
            }
        }
        
        function showAdditionalData(participant) {
            // Create a modal to show additional data
            const modal = document.createElement('div');
            modal.style.position = 'fixed';
            modal.style.top = '0';
            modal.style.left = '0';
            modal.style.width = '100%';
            modal.style.height = '100%';
            modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
            modal.style.display = 'flex';
            modal.style.justifyContent = 'center';
            modal.style.alignItems = 'center';
            modal.style.zIndex = '1000';
            
            const content = document.createElement('div');
            content.style.backgroundColor = 'white';
            content.style.padding = '20px';
            content.style.borderRadius = '5px';
            content.style.width = '80%';
            content.style.maxWidth = '600px';
            content.style.maxHeight = '80%';
            content.style.overflowY = 'auto';
            
            const closeBtn = document.createElement('button');
            closeBtn.textContent = 'Close';
            closeBtn.style.float = 'right';
            closeBtn.onclick = () => document.body.removeChild(modal);
            
            // Create table HTML for participant data
            let tableHTML = `
                <h3>Data for ${participant.phone_number}</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <tr>
                        <th style="text-align: left; padding: 8px; border-bottom: 1px solid #ddd;">Field</th>
                        <th style="text-align: left; padding: 8px; border-bottom: 1px solid #ddd;">Value</th>
                    </tr>
            `;
            
            // Add core fields first
            tableHTML += `
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">Phone Number</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.phone_number || 'N/A'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">Consent Status</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.consent_status || 'N/A'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">Email</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.email || 'N/A'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">Survey Sent</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant.survey_sent ? 'Yes' : 'No'}</td>
                </tr>
            `;
            
            // Add other fields excluding system fields
            const systemFields = ['id', 'phone_number', 'consent_status', 'consent_timestamp', 'email', 'survey_sent', 'created_at'];
            
            for (const key in participant) {
                if (!systemFields.includes(key) && participant[key] !== null) {
                    tableHTML += `
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">${key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">${participant[key]}</td>
                        </tr>
                    `;
                }
            }
            
            tableHTML += '</table>';
            
            content.innerHTML = tableHTML;
            content.appendChild(closeBtn);
            modal.appendChild(content);
            document.body.appendChild(modal);
            
            // Close when clicking outside the modal
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    document.body.removeChild(modal);
                }
            });
        }
        
        async function viewDetailedData() {
            try {
                const response = await fetch(`${API_BASE}/participants`);
                const result = await response.json();
                
                if (result.status === 'success') {
                    // Create table header
                    const headerRow = document.createElement('tr');
                    const fullDataHeader = document.getElementById('fullDataHeader');
                    fullDataHeader.innerHTML = '';
                    
                    // Determine all possible columns
                    const allColumns = new Set();
                    
                    // Add core columns first
                    const coreColumns = ['phone_number', 'consent_status', 'email', 'survey_sent'];
                    coreColumns.forEach(col => allColumns.add(col));
                    
                    // Add all other columns from all participants
                    result.data.forEach(participant => {
                        Object.keys(participant).forEach(key => {
                            // Skip system columns
                            if (!['id', 'consent_timestamp', 'created_at'].includes(key)) {
                                allColumns.add(key);
                            }
                        });
                    });
                    
                    // Create header cells
                    Array.from(allColumns).forEach(column => {
                        const th = document.createElement('th');
                        th.textContent = column.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        headerRow.appendChild(th);
                    });
                    
                    fullDataHeader.appendChild(headerRow);
                    
                    // Create data rows
                    const tbody = document.getElementById('fullDataBody');
                    tbody.innerHTML = '';
                    
                    if (result.data && result.data.length > 0) {
                        result.data.forEach(participant => {
                            const row = document.createElement('tr');
                            
                            // Add cells for each column
                            Array.from(allColumns).forEach(column => {
                                const cell = document.createElement('td');
                                
                                if (column === 'survey_sent') {
                                    cell.textContent = participant[column] ? 'Yes' : 'No';
                                } else {
                                    cell.textContent = participant[column] || 'N/A';
                                }
                                
                                row.appendChild(cell);
                            });
                            
                            tbody.appendChild(row);
                        });
                    } else {
                        const row = tbody.insertRow();
                        const cell = row.insertCell(0);
                        cell.colSpan = allColumns.size;
                        cell.textContent = 'No participants found';
                        cell.style.textAlign = 'center';
                    }
                    
                    document.getElementById('detailedDataTable').style.display = 'block';
                    showStatus('Detailed data loaded successfully', true);
                } else {
                    showStatus('Error loading detailed data', false);
                }
            } catch (error) {
                showStatus('Error fetching detailed data: ' + error.message, false);
            }
        }
        
        async function loadColumnDefinitions() {
            try {
                const response = await fetch(`${API_BASE}/column_definitions`);
                const result = await response.json();
                
                if (result.status === 'success') {
                    const tbody = document.getElementById('columnDefinitionsBody');
                    tbody.innerHTML = '';
                    
                    if (result.columns && result.columns.length > 0) {
                        result.columns.forEach(column => {
                            const row = tbody.insertRow();
                            
                            // Column name cell
                            row.insertCell(0).textContent = column.column_name;
                            
                            // Display name cell
                            row.insertCell(1).textContent = column.display_name;
                            
                            // Data type cell
                            row.insertCell(2).textContent = column.data_type;
                            
                            // Active status cell
                            const activeCell = row.insertCell(3);
                            const activeCheckbox = document.createElement('input');
                            activeCheckbox.type = 'checkbox';
                            activeCheckbox.checked = column.is_active;
                            activeCheckbox.onchange = () => toggleColumnStatus(column.id, activeCheckbox.checked);
                            activeCell.appendChild(activeCheckbox);
                            
                            // Actions cell
                            const actionsCell = row.insertCell(4);
                            const deleteBtn = document.createElement('button');
                            deleteBtn.textContent = 'Delete';
                            deleteBtn.style.backgroundColor = '#dc3545';
                            deleteBtn.style.padding = '3px 8px';
                            deleteBtn.style.fontSize = '12px';
                            deleteBtn.onclick = () => deleteColumn(column.id, column.column_name);
                            actionsCell.appendChild(deleteBtn);
                        });
                    } else {
                        const row = tbody.insertRow();
                        const cell = row.insertCell(0);
                        cell.colSpan = 5;
                        cell.textContent = 'No custom columns defined';
                        cell.style.textAlign = 'center';
                    }
                    
                    document.getElementById('columnsTable').style.display = 'block';
                    showStatus('Column definitions loaded successfully', true);
                } else {
                    showStatus('Error loading column definitions', false);
                }
            } catch (error) {
                showStatus('Error fetching column definitions: ' + error.message, false);
            }
        }
        
        async function toggleColumnStatus(columnId, isActive) {
            try {
                const response = await fetch(`${API_BASE}/toggle_column`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        column_id: columnId,
                        is_active: isActive
                    })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showStatus(`Column status updated successfully`, true);
                } else {
                    showStatus(result.message || 'Error updating column status', false);
                    // Reload to show current state
                    loadColumnDefinitions();
                }
            } catch (error) {
                showStatus('Error updating column status: ' + error.message, false);
            }
        }
        
        async function deleteColumn(columnId, columnName) {
            if (!confirm(`Are you sure you want to delete the column "${columnName}"? This cannot be undone!`)) {
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE}/delete_column`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        column_id: columnId
                    })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showStatus(`Column "${columnName}" deleted successfully`, true);
                    loadColumnDefinitions();
                } else {
                    showStatus(result.message || 'Error deleting column', false);
                }
            } catch (error) {
                showStatus('Error deleting column: ' + error.message, false);
            }
        }
        
        async function addNewColumn() {
            const columnName = document.getElementById('newColumnName').value.trim();
            const displayName = document.getElementById('newDisplayName').value.trim();
            const dataType = document.getElementById('newDataType').value;
            
            if (!columnName) {
                showStatus('Please enter a column name', false);
                return;
            }
            
            // Validate column name format (lowercase, numbers, underscores only)
            if (!/^[a-z0-9_]+$/.test(columnName)) {
                showStatus('Column name must contain only lowercase letters, numbers, and underscores', false);
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE}/add_column`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        column_name: columnName,
                        display_name: displayName || null,
                        data_type: dataType
                    })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showStatus(result.message, true);
                    
                    // Clear input fields
                    document.getElementById('newColumnName').value = '';
                    document.getElementById('newDisplayName').value = '';
                    
                    // Reload column definitions
                    loadColumnDefinitions();
                } else {
                    showStatus(result.message, false);
                }
            } catch (error) {
                showStatus('Error adding column: ' + error.message, false);
            }
        }

        async function checkHealth() {
            try {
                const response = await fetch(`${API_BASE}/health`);
                const result = await response.json();
                
                const healthStatus = document.getElementById('healthStatus');
                if (result.status === 'healthy') {
                    healthStatus.innerHTML = `
                        <div style="color: green;">
                            <strong>✅ App is healthy!</strong><br>
                            Timestamp: ${result.timestamp}<br>
                            Database: ${result.database ? 'Connected' : 'Not connected'}
                        </div>
                    `;
                    showStatus('Health check successful', true);
                } else {
                    healthStatus.innerHTML = `<div style="color: red;">❌ App is unhealthy</div>`;
                    showStatus('Health check failed', false);
                }
                
                document.getElementById('healthInfo').style.display = 'block';
            } catch (error) {
                showStatus('Error checking health: ' + error.message, false);
            }
        }

        async function clearDatabase() {
            if (!confirm('Are you sure you want to delete ALL participants and responses? This cannot be undone!')) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/clear_database`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
                
                // Refresh participants view if it's open
                if (document.getElementById('participantsTable').style.display !== 'none') {
                    viewParticipants();
                }
                
                // Refresh detailed data view if it's open
                if (document.getElementById('detailedDataTable').style.display !== 'none') {
                    viewDetailedData();
                }
            } catch (error) {
                showStatus('Error clearing database: ' + error.message, false);
            }
        }

        async function resetSurveySent() {
            if (!confirm('Reset survey sent status for all participants?')) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/reset_survey_status`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                showStatus(result.message, response.ok);
                
                // Refresh participants view if it's open
                if (document.getElementById('participantsTable').style.display !== 'none') {
                    viewParticipants();
                }
                
                // Refresh detailed data view if it's open
                if (document.getElementById('detailedDataTable').style.display !== 'none') {
                    viewDetailedData();
                }
            } catch (error) {
                showStatus('Error resetting survey status: ' + error.message, false);
            }
        }

        function exportData() {
            showStatus('Starting data export...', true);
            
            // Create a hidden iframe to trigger the download without navigating away
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            document.body.appendChild(iframe);
            
            // Set the source to the export endpoint
            iframe.src = `${API_BASE}/export_data`;
            
            // Notify the user
            setTimeout(() => {
                showStatus('Download started. Check your downloads folder.', true);
                
                // Clean up the iframe after download has started
                setTimeout(() => {
                    document.body.removeChild(iframe);
                }, 5000);
            }, 1000);
        }
    </script>
</body>
</html>'''
            import os
import sqlite3
import re
import csv
import io
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, Response, session
import requests

# Initialize Flask app
app = Flask(__name__)

# Database path
DB_PATH = "survey_responses.db"

def init_database():
    """Initialize database with required tables and dynamic column handling"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE csv_columns SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, column_id)
        )
        conn.commit()
        
        # Ensure columns are updated in the database
        ensure_dynamic_columns()
        
        return jsonify({
            "status": "success",
            "message": f"Column status updated successfully"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/add_column', methods=['POST'])
def add_column():
    """Add a new custom column definition"""
    data = request.get_json()
    
    if not data or 'column_name' not in data:
        return jsonify({"status": "error", "message": "Column name required"}), 400
    
    column_name = data['column_name'].lower().replace(' ', '_')
    display_name = data.get('display_name', None)
    data_type = data.get('data_type', 'TEXT')
    
    # Validate column name (only allow alphanumeric and underscore)
    if not re.match(r'^[a-z0-9_]+PATH)
    cursor = conn.cursor()
    
    # Create participants table with essential columns only
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE,
            consent_status TEXT DEFAULT 'pending',
            consent_timestamp DATETIME,
            email TEXT,
            survey_sent INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create responses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            message_body TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create metadata table to store column definitions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS csv_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_name TEXT UNIQUE,
            display_name TEXT,
            data_type TEXT DEFAULT 'TEXT',
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Ensure dynamic columns exist in the participants table
    ensure_dynamic_columns()

def ensure_dynamic_columns():
    """Check for any columns in csv_columns and add them to participants table if missing"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get list of active columns from csv_columns
        cursor.execute("SELECT column_name, data_type FROM csv_columns WHERE is_active = 1")
        columns = cursor.fetchall()
        
        # Get current columns in participants table
        cursor.execute("PRAGMA table_info(participants)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        # Add any missing columns
        for col_name, data_type in columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE participants ADD COLUMN {col_name} {data_type}")
                    print(f"Added column {col_name} to participants table")
                except Exception as e:
                    print(f"Error adding column {col_name}: {e}")
        
        conn.commit()
    except Exception as e:
        print(f"Error ensuring dynamic columns: {e}")
    finally:
        conn.close()

def get_column_definitions():
    """Get active column definitions from csv_columns table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT column_name, display_name FROM csv_columns WHERE is_active = 1")
        columns = {col[0]: col[1] for col in cursor.fetchall()}
        return columns
    except Exception as e:
        print(f"Error getting column definitions: {e}")
        return {}
    finally:
        conn.close()

def add_column_definition(column_name, display_name=None, data_type="TEXT"):
    """Add a new column definition to csv_columns table if it doesn't exist"""
    if not display_name:
        # Convert snake_case to Title Case
        display_name = ' '.join(word.capitalize() for word in column_name.split('_'))
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("SELECT column_name FROM csv_columns WHERE column_name = ?", (column_name,))
        existing = cursor.fetchone()
        
        if not existing:
            # Add new column definition
            cursor.execute(
                "INSERT INTO csv_columns (column_name, display_name, data_type) VALUES (?, ?, ?)", 
                (column_name, display_name, data_type)
            )
            conn.commit()
            
            # Add column to participants table
            try:
                cursor.execute(f"ALTER TABLE participants ADD COLUMN {col_name} {data_type}")
            except:
                pass  # Column might already exist or there might be an issue with SQLite
            
            conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Error adding column definition: {e}")
        return False
    finally:
        conn.close()

def process_csv_file(file_content):
    """Process CSV file content, detect columns, and return structure for column selection"""
    try:
        # Try to decode the file content as UTF-8
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Try to read the CSV file
        reader = csv.reader(csv_file)
        
        # Get all rows
        rows = list(reader)
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # First row is assumed to be header
        headers = [h.strip() for h in rows[0]]
        
        # Create preview data for column selection
        preview_data = []
        for i in range(1, min(6, len(rows))):  # Preview first 5 rows
            if i < len(rows):
                row_data = {}
                for j, header in enumerate(headers):
                    if j < len(rows[i]):
                        row_data[header] = rows[i][j]
                    else:
                        row_data[header] = ""
                preview_data.append(row_data)
        
        # Identify phone number column
        phone_column = None
        for header in headers:
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in ['phone', 'mobile', 'cell', 'contact', 'number', 'tel']):
                phone_column = header
                break
        
        # If no phone column found, guess it's the first column
        if not phone_column and headers:
            phone_column = headers[0]
        
        return {
            "status": "success",
            "headers": headers,
            "phone_column": phone_column,
            "preview_data": preview_data,
            "total_rows": len(rows) - 1  # Exclude header row
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

def save_selected_csv_data(file_content, phone_column, selected_columns):
    """Save data from CSV based on selected columns"""
    try:
        # Decode the file content
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Read the CSV file
        reader = csv.reader(csv_file)
        rows = list(reader)
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # Get headers and their indices
        headers = [h.strip() for h in rows[0]]
        column_indices = {}
        
        # Map selected column names to their indices
        for col in selected_columns:
            if col in headers:
                column_indices[col] = headers.index(col)
        
        # Get phone column index
        if phone_column not in headers:
            return {"status": "error", "message": f"Phone column '{phone_column}' not found in CSV"}
        
        phone_idx = headers.index(phone_column)
        
        # Process each row and extract data
        processed_data = []
        for row in rows[1:]:  # Skip header row
            if len(row) <= phone_idx or not row[phone_idx].strip():
                continue  # Skip rows with no phone number
                
            phone = row[phone_idx].strip()
            if not is_valid_phone_number(phone):
                continue  # Skip invalid phone numbers
            
            # Create data entry with phone number
            entry = {"phone": normalize_phone_number(phone)}
            
            # Add selected column data
            for col_name, col_idx in column_indices.items():
                if col_idx < len(row):
                    # Convert column name to snake_case for database storage
                    db_col_name = col_name.lower().replace(' ', '_')
                    entry[db_col_name] = row[col_idx].strip()
                    
                    # Add column definition if it doesn't exist
                    add_column_definition(db_col_name, col_name)
            
            processed_data.append(entry)
        
        # Save data to database
        save_data_to_db(processed_data)
        
        # Return just the phone numbers for consent sending
        phone_numbers = [entry["phone"] for entry in processed_data]
        
        # Remove duplicates while preserving order
        unique_phones = []
        seen = set()
        for phone in phone_numbers:
            if phone not in seen:
                seen.add(phone)
                unique_phones.append(phone)
                
        return {
            "status": "success", 
            "phone_numbers": unique_phones,
            "total": len(unique_phones)
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

def save_data_to_db(data_entries):
    """Save all data entries to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for entry in data_entries:
        try:
            # Get the phone number
            phone = entry.pop("phone")
            
            # Check if phone number already exists
            cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (phone,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing entry with new data
                update_parts = []
                update_values = []
                
                for key, value in entry.items():
                    update_parts.append(f"{key} = ?")
                    update_values.append(value)
                
                # Only proceed if there are fields to update
                if update_parts:
                    update_values.append(phone)  # Add phone number for WHERE clause
                    update_sql = f"UPDATE participants SET {', '.join(update_parts)} WHERE phone_number = ?"
                    cursor.execute(update_sql, update_values)
            else:
                # Insert new entry
                columns = ["phone_number"] + list(entry.keys())
                placeholders = ["?"] * len(columns)
                values = [phone] + list(entry.values())
                
                insert_sql = f"INSERT INTO participants ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(insert_sql, values)
        except Exception as e:
            print(f"Error saving entry for {phone}: {e}")
            
    conn.commit()
    conn.close()

def send_sms(to_number, message_body):
    """Send SMS using Twilio API"""
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    phone_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    if not all([account_sid, auth_token, phone_number]):
        print("ERROR: Twilio credentials not set")
        return False
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    
    response = requests.post(
        url,
        auth=(account_sid, auth_token),
        data={
            'To': to_number,
            'From': phone_number,
            'Body': message_body
        }
    )
    
    if response.status_code == 201:
        print(f"SMS sent successfully to {to_number}")
        return True
    else:
        print(f"Failed to send SMS to {to_number}. Status: {response.status_code}")
        return False

def process_sms_response(from_number, message_body):
    """Process incoming SMS response"""
    print(f"Processing response from {from_number}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Log the response
        cursor.execute(
            "INSERT INTO responses (phone_number, message_body) VALUES (?, ?)",
            (from_number, message_body)
        )
        
        # Process the response
        message_upper = message_body.strip().upper()
        print(f"Processing message: '{message_upper}'")
        
        # Check if the participant exists in the database with EXACT match
        cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (from_number,))
        participant = cursor.fetchone()
        
        if not participant:
            print(f"Searching for alternative formats for number {from_number}")
            # Try searching for the number without the '+' prefix
            if from_number.startswith('+'):
                alt_number = from_number[1:]  # Remove the '+' prefix
                cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (alt_number,))
                participant = cursor.fetchone()
            
            # Try searching with '+' prefix
            if not participant and not from_number.startswith('+') and from_number.isdigit():
                alt_number = '+' + from_number
                cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (alt_number,))
                participant = cursor.fetchone()
                
            # If we still can't find it, try removing the country code if it's there
            if not participant and (from_number.startswith('+1') or from_number.startswith('1')):
                if from_number.startswith('+1'):
                    alt_number = from_number[2:]  # Remove the '+1' prefix
                elif from_number.startswith('1'):
                    alt_number = from_number[1:]  # Remove the '1' prefix
                cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (alt_number,))
                participant = cursor.fetchone()
                
            if not participant:
                print(f"No participant found for number {from_number} after trying alternative formats")
                # Send a message that we couldn't identify them
                help_msg = "We couldn't identify your number in our system. Please text START to join our survey list."
                send_sms(from_number, help_msg)
                return
        
        # Get the actual phone number as stored in database
        stored_number = participant[0]
        print(f"Found participant with number: {stored_number}")
        
        if message_upper == "YES":
            print(f"Processing YES response for {stored_number}")
            # Update consent status
            cursor.execute(
                "UPDATE participants SET consent_status = 'consented', consent_timestamp = CURRENT_TIMESTAMP WHERE phone_number = ?",
                (stored_number,)
            )
            rows_affected = cursor.rowcount
            conn.commit()
            print(f"Updated consent status, rows affected: {rows_affected}")
            
            # Send thank you message
            thank_you_msg = "Thank you for consenting! You'll receive survey links occasionally. Reply STOP anytime to unsubscribe."
            send_result = send_sms(from_number, thank_you_msg)
            print(f"Sent thank you message: {send_result}")
            
        elif message_upper in ["NO", "STOP"]:
            # Update consent status
            cursor.execute(
                "UPDATE participants SET consent_status = 'declined' WHERE phone_number = ?",
                (stored_number,)
            )
            conn.commit()
            
            # Send opt-out confirmation
            opt_out_msg = "You've been removed from our survey list. Thank you!"
            send_sms(from_number, opt_out_msg)
            print(f"Sent opt-out confirmation to {from_number}")
            
        elif message_upper.startswith("EMAIL") or re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message_body):
            # Handle both "EMAIL address@email.com" and plain "address@email.com"
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message_body)
            if email_match:
                email = email_match.group()
                # Update both email AND consent status
                cursor.execute(
                    "UPDATE participants SET email = ?, consent_status = 'consented', consent_timestamp = CURRENT_TIMESTAMP WHERE phone_number = ?",
                    (email, stored_number)
                )
                conn.commit()
                
                # Send confirmation for both email and SMS consent
                email_msg = f"Thanks! We've saved your email: {email}. You're now signed up for email surveys. Reply STOP anytime to unsubscribe."
                send_sms(from_number, email_msg)
                print(f"Sent email and consent confirmation to {from_number}")
        else:
            # Handle unknown responses
            help_msg = "Reply YES to consent to SMS surveys, NO to opt out, or provide your email address to sign up for both SMS and email surveys."
            send_sms(from_number, help_msg)
            print(f"Sent help message to {from_number}")
        
        conn.commit()
    except Exception as e:
        print(f"Error processing response: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def normalize_phone_number(phone):
    """
    Normalize phone number to a consistent format
    Handles cases where carrier might add or remove country code
    """
    # Remove any non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Handle North American numbers (assuming this is for NA market)
    if len(digits_only) == 10:
        # Add US/Canada country code if 10 digits
        return "+1" + digits_only
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        # Add + if it's a standard NA format with country code
        return "+" + digits_only
    elif digits_only.startswith('+'):
        # Already has + prefix
        return phone
    else:
        # Return as is if we can't normalize it
        return phone

def send_consent_request(phone_numbers):
    """Send consent request to list of phone numbers"""
    consent_message = (
        "Hi! This is Pallas Data. You previously expressed interest in participating in our surveys. "
        "We'd like to text you survey links occasionally. "
        "Reply 'YES' to consent or 'NO' to opt out. "
        "You can also reply with your email address if you want to also get surveys emailed to you. "
        "Thanks!"
    )
    
    results = {"success": [], "failed": []}
    
    for phone in phone_numbers:
        # Clean phone number
        phone = phone.strip()
        if not phone:
            continue
            
        # Validate phone number format
        if not is_valid_phone_number(phone):
            results["failed"].append({"phone": phone, "reason": "Invalid phone number format"})
            continue
        
        # Phone number is valid, so proceed
        normalized_phone = normalize_phone_number(phone)
        
        # Add to database - this will now be handled by the CSV processing function
        # to include the additional fields
        
        # Send SMS
        if send_sms(normalized_phone, consent_message):
            results["success"].append(normalized_phone)
        else:
            results["failed"].append({"phone": normalized_phone, "reason": "Failed to send SMS"})
        
        # Add small delay for rate limiting
        import time
        time.sleep(1)
    
    return results

def is_valid_phone_number(phone):
    """
    Basic validation for phone numbers
    Accepts formats like: +1234567890, 1234567890, etc.
    """
    # Remove spaces, dashes, and parentheses
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if it's a valid international format (starting with +)
    if clean_phone.startswith('+'):
        return re.match(r'^\+\d{10,15}$', clean_phone) is not None
    
    # Check if it's a valid US/CA format (10 digits, optionally starting with 1)
    return re.match(r'^1?\d{10}$', clean_phone) is not None

def send_survey_link(survey_url, custom_message=None):
    """Send survey link to consented participants"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get consented participants who haven't been sent this survey
    cursor.execute(
        "SELECT phone_number FROM participants WHERE consent_status = 'consented' AND survey_sent = 0"
    )
    participants = cursor.fetchall()
    conn.close()
    
    if not participants:
        print("No consented participants to send survey to.")
        return
    
    message = custom_message or f"Hi! Here's your survey link: {survey_url} Thank you for participating!"
    
    for (phone,) in participants:
        if send_sms(phone, message):
            # Mark as survey sent
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE participants SET survey_sent = 1 WHERE phone_number = ?",
                (phone,)
            )
            conn.commit()
            conn.close()
        
        import time
        time.sleep(1)  # Rate limiting

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Twilio webhook"""
    print(f"=== Webhook called at {datetime.now()} ===")
    print(f"Request form data: {request.form}")
    
    # Twilio sends the phone number in the 'From' field
    from_number = request.form.get('From')
    message_body = request.form.get('Body', '').strip()
    
    print(f"From: {from_number}")
    print(f"Message: {message_body}")
    
    # Check if participant exists in database
    if from_number and message_body:
        # Process the response
        process_sms_response(from_number, message_body)
        print("Processing complete!")
    
    # Return TwiML response
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {'Content-Type': 'text/xml'}
    
@app.route('/health')
def health():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': os.path.exists(DB_PATH)
    }

@app.route('/send_consent', methods=['POST'])
def send_consent_endpoint():
    """Endpoint to send consent request"""
    phone_number = request.form.get('phone_number')
    if phone_number:
        normalized_phone = normalize_phone_number(phone_number)
        
        # Send the consent message
        results = send_consent_request([normalized_phone])
        if normalized_phone in results["success"]:
            return {'status': 'success', 'message': f'Consent request sent to {normalized_phone}'}
        else:
            failed_entry = next((entry for entry in results["failed"] if entry["phone"] == normalized_phone), None)
            reason = failed_entry["reason"] if failed_entry else "Unknown error"
            return {'status': 'error', 'message': f'Failed to send consent request: {reason}'}, 400
    
    return {'status': 'error', 'message': 'Phone number required'}, 400

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Handle CSV upload and process structure for column selection"""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({"status": "error", "message": "File must be a CSV"}), 400
    
    try:
        # Read the file content
        file_content = file.read()
        
        # Store file content in session for later use
        session_id = str(uuid.uuid4())
        temp_file_path = os.path.join('/tmp', f'csv_upload_{session_id}.csv')
        with open(temp_file_path, 'wb') as f:
            f.write(file_content)
        
        # Process the CSV file to get structure
        result = process_csv_file(file_content)
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Return the CSV structure for column selection
        return jsonify({
            "status": "success",
            "message": "CSV uploaded successfully. Please select columns to import.",
            "session_id": session_id,
            "headers": result["headers"],
            "phone_column": result["phone_column"],
            "preview_data": result["preview_data"],
            "total_rows": result["total_rows"]
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error processing file: {str(e)}"}), 500

@app.route('/process_selected_columns', methods=['POST'])
def process_selected_columns():
    """Process CSV data based on selected columns"""
    data = request.get_json()
    
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    session_id = data.get('session_id')
    phone_column = data.get('phone_column')
    selected_columns = data.get('selected_columns', [])
    send_consent = data.get('send_consent', False)
    
    if not session_id or not phone_column:
        return jsonify({"status": "error", "message": "Missing required parameters"}), 400
    
    # Load the CSV file from temporary storage
    temp_file_path = os.path.join('/tmp', f'csv_upload_{session_id}.csv')
    
    if not os.path.exists(temp_file_path):
        return jsonify({"status": "error", "message": "CSV file not found. Please upload again."}), 400
    
    try:
        with open(temp_file_path, 'rb') as f:
            file_content = f.read()
        
        # Process the selected columns
        result = save_selected_csv_data(file_content, phone_column, selected_columns)
        
        # Clean up the temporary file
        try:
            os.remove(temp_file_path)
        except:
            pass
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Send consent messages if requested
        if send_consent and result["phone_numbers"]:
            send_results = send_consent_request(result["phone_numbers"])
            
            return jsonify({
                "status": "success",
                "message": f"Processed CSV and sent consent requests",
                "total_numbers": result["total"],
                "selected_columns": selected_columns,
                "successful_sends": len(send_results["success"]),
                "failed_sends": len(send_results["failed"]),
                "failures": send_results["failed"]
            })
        
        # Return the results
        return jsonify({
            "status": "success",
            "message": f"Successfully saved data for {result['total']} participants",
            "selected_columns": selected_columns,
            "phone_numbers": result["phone_numbers"],
            "total": result["total"]
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error processing selected columns: {str(e)}"}), 500

@app.route('/column_definitions', methods=['GET'])
def get_column_definitions_route():
    """Get all column definitions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, column_name, display_name, data_type, is_active FROM csv_columns")
        columns = cursor.fetchall()
        
        column_list = []
        for col in columns:
            column_list.append({
                "id": col[0],
                "column_name": col[1],
                "display_name": col[2],
                "data_type": col[3],
                "is_active": bool(col[4])
            })
        
        return jsonify({
            "status": "success",
            "columns": column_list
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/toggle_column', methods=['POST'])
def toggle_column():
    """Toggle a column's active status"""
    data = request.get_json()
    
    if not data or 'column_id' not in data:
        return jsonify({"status": "error", "message": "Column ID required"}), 400
    
    column_id = data['column_id']
    is_active = data.get('is_active', True)
    
    conn = sqlite3.connect(DB_, column_name):
        return jsonify({"status": "error", "message": "Column name can only contain lowercase letters, numbers, and underscores"}), 400
    
    # Add the column definition
    if add_column_definition(column_name, display_name, data_type):
        return jsonify({
            "status": "success", 
            "message": f"Column '{column_name}' added successfully"
        })
    else:
        return jsonify({
            "status": "error", 
            "message": f"Column '{column_name}' already exists or could not be added"
        }), 400

@app.route('/delete_column', methods=['POST'])
def delete_column():
    """Delete a column definition"""
    data = request.get_json()
    
    if not data or 'column_id' not in data:
        return jsonify({"status": "error", "message": "Column ID required"}), 400
    
    column_id = data['column_id']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # First get the column name
        cursor.execute("SELECT column_name FROM csv_columns WHERE id = ?", (column_id,))
        column = cursor.fetchone()
        
        if not column:
            return jsonify({"status": "error", "message": "Column not found"}), 404
        
        column_name = column[0]
        
        # Delete the column definition
        cursor.execute("DELETE FROM csv_columns WHERE id = ?", (column_id,))
        conn.commit()
        
        # We can't easily drop columns in SQLite, but we can mark that this column should no longer be used
        
        return jsonify({
            "status": "success",
            "message": f"Column deleted successfully"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/participants')
def participants():
    """Get all participants with dynamic column support"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM participants")
    rows = cursor.fetchall()
    
    # Get column names dynamically
    column_names = [description[0] for description in cursor.description]
    
    # Create a list of dictionaries
    participants_list = []
    for row in rows:
        participant_dict = {}
        for i, value in enumerate(row):
            participant_dict[column_names[i]] = value
        participants_list.append(participant_dict)
    
    conn.close()
    
    return {
        'status': 'success',
        'data': participants_list,
        'columns': column_names
    }

@app.route('/send_bulk_consent', methods=['POST'])
def send_bulk_consent():
    """Send consent requests to a list of phone numbers"""
    data = request.get_json()
    if not data or 'phone_numbers' not in data or not isinstance(data['phone_numbers'], list):
        return jsonify({"status": "error", "message": "Phone numbers list required"}), 400
    
    phone_numbers = data['phone_numbers']
    if not phone_numbers:
        return jsonify({"status": "error", "message": "Phone numbers list is empty"}), 400
    
    # Send consent requests
    results = send_consent_request(phone_numbers)
    
    return jsonify({
        "status": "success",
        "message": f"Consent requests sent",
        "total_numbers": len(phone_numbers),
        "successful_sends": len(results["success"]),
        "failed_sends": len(results["failed"]),
        "failures": results["failed"]
    })

@app.route('/send_survey', methods=['POST'])
def send_survey_endpoint():
    """Endpoint to send survey link"""
    survey_url = request.form.get('survey_url')
    custom_message = request.form.get('custom_message')
    
    if survey_url:
        send_survey_link(survey_url, custom_message)
        return {'status': 'success', 'message': 'Survey sent to consented participants'}
    return {'status': 'error', 'message': 'Survey URL required'}, 400

@app.route('/clear_database', methods=['POST'])
def clear_database():
    """Clear all data from the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Delete all participants
        cursor.execute("DELETE FROM participants")
        # Delete all responses  
        cursor.execute("DELETE FROM responses")
        # Reset auto-increment counters
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='participants'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='responses'")
        
        conn.commit()
        return {'status': 'success', 'message': 'Database cleared successfully'}
    except Exception as e:  
        return {'status': 'error', 'message': 'Error clearing database: ' + str(e)}, 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/reset_survey_status', methods=['POST'])
def reset_survey_status():
    """Reset survey_sent status for all participants"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE participants SET survey_sent = 0")
        rows_affected = cursor.rowcount
        conn.commit()
        return {'status': 'success', 'message': 'Reset survey status for ' + str(rows_affected) + ' participants'}
    except Exception as e:
        return {'status': 'error', 'message': 'Error resetting survey status: ' + str(e)}, 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/export_data', methods=['GET'])
def export_data():
    """Export all data to a CSV file"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all participants with all columns
        cursor.execute("SELECT * FROM participants")
        participants = cursor.fetchall()
        participant_columns = [description[0] for description in cursor.description]
        
        # Get all responses
        cursor.execute("SELECT * FROM responses")
        responses = cursor.fetchall()
        response_columns = [description[0] for description in cursor.description]
        
        conn.close()
        
        # Create a CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write participants section
        writer.writerow(['## PARTICIPANTS'])
        writer.writerow(participant_columns)
        for row in participants:
            writer.writerow(row)
        
        # Add a separator
        writer.writerow([])
        writer.writerow(['## RESPONSES'])
        
        # Write responses section
        writer.writerow(response_columns)
        for row in responses:
            writer.writerow(row)
        
        # Prepare response
        output.seek(0)
        csv_data = output.getvalue()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"survey_data_{timestamp}.csv"
        
        # Return the CSV file as a downloadable attachment
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    except Exception as e:
        print(f"Error exporting data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500PATH)
    cursor = conn.cursor()
    
    # Create participants table with essential columns only
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE,
            consent_status TEXT DEFAULT 'pending',
            consent_timestamp DATETIME,
            email TEXT,
            survey_sent INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create responses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            message_body TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create metadata table to store column definitions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS csv_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_name TEXT UNIQUE,
            display_name TEXT,
            data_type TEXT DEFAULT 'TEXT',
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Ensure dynamic columns exist in the participants table
    ensure_dynamic_columns()

def ensure_dynamic_columns():
    """Check for any columns in csv_columns and add them to participants table if missing"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get list of active columns from csv_columns
        cursor.execute("SELECT column_name, data_type FROM csv_columns WHERE is_active = 1")
        columns = cursor.fetchall()
        
        # Get current columns in participants table
        cursor.execute("PRAGMA table_info(participants)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        # Add any missing columns
        for col_name, data_type in columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE participants ADD COLUMN {col_name} {data_type}")
                    print(f"Added column {col_name} to participants table")
                except Exception as e:
                    print(f"Error adding column {col_name}: {e}")
        
        conn.commit()
    except Exception as e:
        print(f"Error ensuring dynamic columns: {e}")
    finally:
        conn.close()

def get_column_definitions():
    """Get active column definitions from csv_columns table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT column_name, display_name FROM csv_columns WHERE is_active = 1")
        columns = {col[0]: col[1] for col in cursor.fetchall()}
        return columns
    except Exception as e:
        print(f"Error getting column definitions: {e}")
        return {}
    finally:
        conn.close()

def add_column_definition(column_name, display_name=None, data_type="TEXT"):
    """Add a new column definition to csv_columns table if it doesn't exist"""
    if not display_name:
        # Convert snake_case to Title Case
        display_name = ' '.join(word.capitalize() for word in column_name.split('_'))
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("SELECT column_name FROM csv_columns WHERE column_name = ?", (column_name,))
        existing = cursor.fetchone()
        
        if not existing:
            # Add new column definition
            cursor.execute(
                "INSERT INTO csv_columns (column_name, display_name, data_type) VALUES (?, ?, ?)", 
                (column_name, display_name, data_type)
            )
            conn.commit()
            
            # Add column to participants table
            try:
                cursor.execute(f"ALTER TABLE participants ADD COLUMN {col_name} {data_type}")
            except:
                pass  # Column might already exist or there might be an issue with SQLite
            
            conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Error adding column definition: {e}")
        return False
    finally:
        conn.close()

def process_csv_file(file_content):
    """Process CSV file content, detect columns, and return structure for column selection"""
    try:
        # Try to decode the file content as UTF-8
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Try to read the CSV file
        reader = csv.reader(csv_file)
        
        # Get all rows
        rows = list(reader)
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # First row is assumed to be header
        headers = [h.strip() for h in rows[0]]
        
        # Create preview data for column selection
        preview_data = []
        for i in range(1, min(6, len(rows))):  # Preview first 5 rows
            if i < len(rows):
                row_data = {}
                for j, header in enumerate(headers):
                    if j < len(rows[i]):
                        row_data[header] = rows[i][j]
                    else:
                        row_data[header] = ""
                preview_data.append(row_data)
        
        # Identify phone number column
        phone_column = None
        for header in headers:
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in ['phone', 'mobile', 'cell', 'contact', 'number', 'tel']):
                phone_column = header
                break
        
        # If no phone column found, guess it's the first column
        if not phone_column and headers:
            phone_column = headers[0]
        
        return {
            "status": "success",
            "headers": headers,
            "phone_column": phone_column,
            "preview_data": preview_data,
            "total_rows": len(rows) - 1  # Exclude header row
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

def save_selected_csv_data(file_content, phone_column, selected_columns):
    """Save data from CSV based on selected columns"""
    try:
        # Decode the file content
        if isinstance(file_content, bytes):
            file_content = file_content.decode('utf-8')
        
        # Use StringIO to create a file-like object
        csv_file = io.StringIO(file_content)
        
        # Read the CSV file
        reader = csv.reader(csv_file)
        rows = list(reader)
        
        if not rows:
            return {"status": "error", "message": "CSV file is empty"}
        
        # Get headers and their indices
        headers = [h.strip() for h in rows[0]]
        column_indices = {}
        
        # Map selected column names to their indices
        for col in selected_columns:
            if col in headers:
                column_indices[col] = headers.index(col)
        
        # Get phone column index
        if phone_column not in headers:
            return {"status": "error", "message": f"Phone column '{phone_column}' not found in CSV"}
        
        phone_idx = headers.index(phone_column)
        
        # Process each row and extract data
        processed_data = []
        for row in rows[1:]:  # Skip header row
            if len(row) <= phone_idx or not row[phone_idx].strip():
                continue  # Skip rows with no phone number
                
            phone = row[phone_idx].strip()
            if not is_valid_phone_number(phone):
                continue  # Skip invalid phone numbers
            
            # Create data entry with phone number
            entry = {"phone": normalize_phone_number(phone)}
            
            # Add selected column data
            for col_name, col_idx in column_indices.items():
                if col_idx < len(row):
                    # Convert column name to snake_case for database storage
                    db_col_name = col_name.lower().replace(' ', '_')
                    entry[db_col_name] = row[col_idx].strip()
                    
                    # Add column definition if it doesn't exist
                    add_column_definition(db_col_name, col_name)
            
            processed_data.append(entry)
        
        # Save data to database
        save_data_to_db(processed_data)
        
        # Return just the phone numbers for consent sending
        phone_numbers = [entry["phone"] for entry in processed_data]
        
        # Remove duplicates while preserving order
        unique_phones = []
        seen = set()
        for phone in phone_numbers:
            if phone not in seen:
                seen.add(phone)
                unique_phones.append(phone)
                
        return {
            "status": "success", 
            "phone_numbers": unique_phones,
            "total": len(unique_phones)
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Error processing CSV: {str(e)}"}

def save_data_to_db(data_entries):
    """Save all data entries to the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for entry in data_entries:
        try:
            # Get the phone number
            phone = entry.pop("phone")
            
            # Check if phone number already exists
            cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (phone,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing entry with new data
                update_parts = []
                update_values = []
                
                for key, value in entry.items():
                    update_parts.append(f"{key} = ?")
                    update_values.append(value)
                
                # Only proceed if there are fields to update
                if update_parts:
                    update_values.append(phone)  # Add phone number for WHERE clause
                    update_sql = f"UPDATE participants SET {', '.join(update_parts)} WHERE phone_number = ?"
                    cursor.execute(update_sql, update_values)
            else:
                # Insert new entry
                columns = ["phone_number"] + list(entry.keys())
                placeholders = ["?"] * len(columns)
                values = [phone] + list(entry.values())
                
                insert_sql = f"INSERT INTO participants ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(insert_sql, values)
        except Exception as e:
            print(f"Error saving entry for {phone}: {e}")
            
    conn.commit()
    conn.close()

def send_sms(to_number, message_body):
    """Send SMS using Twilio API"""
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    phone_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    if not all([account_sid, auth_token, phone_number]):
        print("ERROR: Twilio credentials not set")
        return False
    
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    
    response = requests.post(
        url,
        auth=(account_sid, auth_token),
        data={
            'To': to_number,
            'From': phone_number,
            'Body': message_body
        }
    )
    
    if response.status_code == 201:
        print(f"SMS sent successfully to {to_number}")
        return True
    else:
        print(f"Failed to send SMS to {to_number}. Status: {response.status_code}")
        return False

def process_sms_response(from_number, message_body):
    """Process incoming SMS response"""
    print(f"Processing response from {from_number}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Log the response
        cursor.execute(
            "INSERT INTO responses (phone_number, message_body) VALUES (?, ?)",
            (from_number, message_body)
        )
        
        # Process the response
        message_upper = message_body.strip().upper()
        print(f"Processing message: '{message_upper}'")
        
        # Check if the participant exists in the database with EXACT match
        cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (from_number,))
        participant = cursor.fetchone()
        
        if not participant:
            print(f"Searching for alternative formats for number {from_number}")
            # Try searching for the number without the '+' prefix
            if from_number.startswith('+'):
                alt_number = from_number[1:]  # Remove the '+' prefix
                cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (alt_number,))
                participant = cursor.fetchone()
            
            # Try searching with '+' prefix
            if not participant and not from_number.startswith('+') and from_number.isdigit():
                alt_number = '+' + from_number
                cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (alt_number,))
                participant = cursor.fetchone()
                
            # If we still can't find it, try removing the country code if it's there
            if not participant and (from_number.startswith('+1') or from_number.startswith('1')):
                if from_number.startswith('+1'):
                    alt_number = from_number[2:]  # Remove the '+1' prefix
                elif from_number.startswith('1'):
                    alt_number = from_number[1:]  # Remove the '1' prefix
                cursor.execute("SELECT phone_number FROM participants WHERE phone_number = ?", (alt_number,))
                participant = cursor.fetchone()
                
            if not participant:
                print(f"No participant found for number {from_number} after trying alternative formats")
                # Send a message that we couldn't identify them
                help_msg = "We couldn't identify your number in our system. Please text START to join our survey list."
                send_sms(from_number, help_msg)
                return
        
        # Get the actual phone number as stored in database
        stored_number = participant[0]
        print(f"Found participant with number: {stored_number}")
        
        if message_upper == "YES":
            print(f"Processing YES response for {stored_number}")
            # Update consent status
            cursor.execute(
                "UPDATE participants SET consent_status = 'consented', consent_timestamp = CURRENT_TIMESTAMP WHERE phone_number = ?",
                (stored_number,)
            )
            rows_affected = cursor.rowcount
            conn.commit()
            print(f"Updated consent status, rows affected: {rows_affected}")
            
            # Send thank you message
            thank_you_msg = "Thank you for consenting! You'll receive survey links occasionally. Reply STOP anytime to unsubscribe."
            send_result = send_sms(from_number, thank_you_msg)
            print(f"Sent thank you message: {send_result}")
            
        elif message_upper in ["NO", "STOP"]:
            # Update consent status
            cursor.execute(
                "UPDATE participants SET consent_status = 'declined' WHERE phone_number = ?",
                (stored_number,)
            )
            conn.commit()
            
            # Send opt-out confirmation
            opt_out_msg = "You've been removed from our survey list. Thank you!"
            send_sms(from_number, opt_out_msg)
            print(f"Sent opt-out confirmation to {from_number}")
            
        elif message_upper.startswith("EMAIL") or re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message_body):
            # Handle both "EMAIL address@email.com" and plain "address@email.com"
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message_body)
            if email_match:
                email = email_match.group()
                # Update both email AND consent status
                cursor.execute(
                    "UPDATE participants SET email = ?, consent_status = 'consented', consent_timestamp = CURRENT_TIMESTAMP WHERE phone_number = ?",
                    (email, stored_number)
                )
                conn.commit()
                
                # Send confirmation for both email and SMS consent
                email_msg = f"Thanks! We've saved your email: {email}. You're now signed up for email surveys. Reply STOP anytime to unsubscribe."
                send_sms(from_number, email_msg)
                print(f"Sent email and consent confirmation to {from_number}")
        else:
            # Handle unknown responses
            help_msg = "Reply YES to consent to SMS surveys, NO to opt out, or provide your email address to sign up for both SMS and email surveys."
            send_sms(from_number, help_msg)
            print(f"Sent help message to {from_number}")
        
        conn.commit()
    except Exception as e:
        print(f"Error processing response: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def normalize_phone_number(phone):
    """
    Normalize phone number to a consistent format
    Handles cases where carrier might add or remove country code
    """
    # Remove any non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # Handle North American numbers (assuming this is for NA market)
    if len(digits_only) == 10:
        # Add US/Canada country code if 10 digits
        return "+1" + digits_only
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        # Add + if it's a standard NA format with country code
        return "+" + digits_only
    elif digits_only.startswith('+'):
        # Already has + prefix
        return phone
    else:
        # Return as is if we can't normalize it
        return phone

def send_consent_request(phone_numbers):
    """Send consent request to list of phone numbers"""
    consent_message = (
        "Hi! This is Pallas Data. You previously expressed interest in participating in our surveys. "
        "We'd like to text you survey links occasionally. "
        "Reply 'YES' to consent or 'NO' to opt out. "
        "You can also reply with your email address if you want to also get surveys emailed to you. "
        "Thanks!"
    )
    
    results = {"success": [], "failed": []}
    
    for phone in phone_numbers:
        # Clean phone number
        phone = phone.strip()
        if not phone:
            continue
            
        # Validate phone number format
        if not is_valid_phone_number(phone):
            results["failed"].append({"phone": phone, "reason": "Invalid phone number format"})
            continue
        
        # Phone number is valid, so proceed
        normalized_phone = normalize_phone_number(phone)
        
        # Add to database - this will now be handled by the CSV processing function
        # to include the additional fields
        
        # Send SMS
        if send_sms(normalized_phone, consent_message):
            results["success"].append(normalized_phone)
        else:
            results["failed"].append({"phone": normalized_phone, "reason": "Failed to send SMS"})
        
        # Add small delay for rate limiting
        import time
        time.sleep(1)
    
    return results

def is_valid_phone_number(phone):
    """
    Basic validation for phone numbers
    Accepts formats like: +1234567890, 1234567890, etc.
    """
    # Remove spaces, dashes, and parentheses
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if it's a valid international format (starting with +)
    if clean_phone.startswith('+'):
        return re.match(r'^\+\d{10,15}$', clean_phone) is not None
    
    # Check if it's a valid US/CA format (10 digits, optionally starting with 1)
    return re.match(r'^1?\d{10}$', clean_phone) is not None

def send_survey_link(survey_url, custom_message=None):
    """Send survey link to consented participants"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get consented participants who haven't been sent this survey
    cursor.execute(
        "SELECT phone_number FROM participants WHERE consent_status = 'consented' AND survey_sent = 0"
    )
    participants = cursor.fetchall()
    conn.close()
    
    if not participants:
        print("No consented participants to send survey to.")
        return
    
    message = custom_message or f"Hi! Here's your survey link: {survey_url} Thank you for participating!"
    
    for (phone,) in participants:
        if send_sms(phone, message):
            # Mark as survey sent
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE participants SET survey_sent = 1 WHERE phone_number = ?",
                (phone,)
            )
            conn.commit()
            conn.close()
        
        import time
        time.sleep(1)  # Rate limiting

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Twilio webhook"""
    print(f"=== Webhook called at {datetime.now()} ===")
    print(f"Request form data: {request.form}")
    
    # Twilio sends the phone number in the 'From' field
    from_number = request.form.get('From')
    message_body = request.form.get('Body', '').strip()
    
    print(f"From: {from_number}")
    print(f"Message: {message_body}")
    
    # Check if participant exists in database
    if from_number and message_body:
        # Process the response
        process_sms_response(from_number, message_body)
        print("Processing complete!")
    
    # Return TwiML response
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {'Content-Type': 'text/xml'}
    
@app.route('/health')
def health():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': os.path.exists(DB_PATH)
    }

@app.route('/send_consent', methods=['POST'])
def send_consent_endpoint():
    """Endpoint to send consent request"""
    phone_number = request.form.get('phone_number')
    if phone_number:
        normalized_phone = normalize_phone_number(phone_number)
        
        # Send the consent message
        results = send_consent_request([normalized_phone])
        if normalized_phone in results["success"]:
            return {'status': 'success', 'message': f'Consent request sent to {normalized_phone}'}
        else:
            failed_entry = next((entry for entry in results["failed"] if entry["phone"] == normalized_phone), None)
            reason = failed_entry["reason"] if failed_entry else "Unknown error"
            return {'status': 'error', 'message': f'Failed to send consent request: {reason}'}, 400
    
    return {'status': 'error', 'message': 'Phone number required'}, 400

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    """Handle CSV upload and process structure for column selection"""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({"status": "error", "message": "File must be a CSV"}), 400
    
    try:
        # Read the file content
        file_content = file.read()
        
        # Store file content in session for later use
        session_id = str(uuid.uuid4())
        temp_file_path = os.path.join('/tmp', f'csv_upload_{session_id}.csv')
        with open(temp_file_path, 'wb') as f:
            f.write(file_content)
        
        # Process the CSV file to get structure
        result = process_csv_file(file_content)
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Return the CSV structure for column selection
        return jsonify({
            "status": "success",
            "message": "CSV uploaded successfully. Please select columns to import.",
            "session_id": session_id,
            "headers": result["headers"],
            "phone_column": result["phone_column"],
            "preview_data": result["preview_data"],
            "total_rows": result["total_rows"]
        })
    
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error processing file: {str(e)}"}), 500

@app.route('/process_selected_columns', methods=['POST'])
def process_selected_columns():
    """Process CSV data based on selected columns"""
    data = request.get_json()
    
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    session_id = data.get('session_id')
    phone_column = data.get('phone_column')
    selected_columns = data.get('selected_columns', [])
    send_consent = data.get('send_consent', False)
    
    if not session_id or not phone_column:
        return jsonify({"status": "error", "message": "Missing required parameters"}), 400
    
    # Load the CSV file from temporary storage
    temp_file_path = os.path.join('/tmp', f'csv_upload_{session_id}.csv')
    
    if not os.path.exists(temp_file_path):
        return jsonify({"status": "error", "message": "CSV file not found. Please upload again."}), 400
    
    try:
        with open(temp_file_path, 'rb') as f:
            file_content = f.read()
        
        # Process the selected columns
        result = save_selected_csv_data(file_content, phone_column, selected_columns)
        
        # Clean up the temporary file
        try:
            os.remove(temp_file_path)
        except:
            pass
        
        if result["status"] == "error":
            return jsonify(result), 400
        
        # Send consent messages if requested
        if send_consent and result["phone_numbers"]:
            send_results = send_consent_request(result["phone_numbers"])
            
            return jsonify({
                "status": "success",
                "message": f"Processed CSV and sent consent requests",
                "total_numbers": result["total"],
                "selected_columns": selected_columns,
                "successful_sends": len(send_results["success"]),
                "failed_sends": len(send_results["failed"]),
                "failures": send_results["failed"]
            })
        
        # Return the results
        return jsonify({
            "status": "success",
            "message": f"Successfully saved data for {result['total']} participants",
            "selected_columns": selected_columns,
            "phone_numbers": result["phone_numbers"],
            "total": result["total"]
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error processing selected columns: {str(e)}"}), 500

@app.route('/column_definitions', methods=['GET'])
def get_column_definitions_route():
    """Get all column definitions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, column_name, display_name, data_type, is_active FROM csv_columns")
        columns = cursor.fetchall()
        
        column_list = []
        for col in columns:
            column_list.append({
                "id": col[0],
                "column_name": col[1],
                "display_name": col[2],
                "data_type": col[3],
                "is_active": bool(col[4])
            })
        
        return jsonify({
            "status": "success",
            "columns": column_list
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/toggle_column', methods=['POST'])
def toggle_column():
    """Toggle a column's active status"""
    data = request.get_json()
    
    if not data or 'column_id' not in data:
        return jsonify({"status": "error", "message": "Column ID required"}), 400
    
    column_id = data['column_id']
    is_active = data.get('is_active', True)
    
    conn = sqlite3.connect(DB_
