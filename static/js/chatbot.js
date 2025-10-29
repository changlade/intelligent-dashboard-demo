// Danone POS Analytics - Chatbot JavaScript

// State management
let currentConversationId = null;
let isProcessing = false;

// DOM elements
const chatMessages = document.getElementById('chatMessages');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');

// Initialize chatbot
document.addEventListener('DOMContentLoaded', () => {
    console.log('Chatbot initialized');
    
    // Handle form submission
    chatForm.addEventListener('submit', handleSubmit);
    
    // Handle Enter key (without Shift)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!isProcessing && chatInput.value.trim()) {
                chatForm.dispatchEvent(new Event('submit'));
            }
        }
    });
});

// Handle form submission
async function handleSubmit(e) {
    e.preventDefault();
    
    const message = chatInput.value.trim();
    if (!message || isProcessing) return;
    
    // Clear input and disable form
    chatInput.value = '';
    setProcessing(true);
    
    // Add user message to chat
    addMessage(message, 'user');
    
    try {
        if (!currentConversationId) {
            // Start new conversation
            await startConversation(message);
        } else {
            // Send follow-up message
            await sendFollowup(message);
        }
    } catch (error) {
        console.error('Chat error:', error);
        addMessage(`Error: ${error.message}. Please try again.`, 'error');
    } finally {
        setProcessing(false);
    }
}

// Start new conversation
async function startConversation(message) {
    try {
        const response = await fetch('/api/genie/conversations/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content: message })
        });
        
        const result = await response.json();
        
        if (result.status === 'success' && result.data) {
            currentConversationId = result.data.conversation_id;
            const messageId = result.data.message_id;
            
            // Poll for the response
            await pollForMessage(currentConversationId, messageId);
        } else {
            throw new Error(result.error || 'Failed to start conversation');
        }
    } catch (error) {
        console.error('Start conversation error:', error);
        throw error;
    }
}

// Send follow-up message
async function sendFollowup(message) {
    try {
        const response = await fetch(`/api/genie/conversations/${currentConversationId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content: message })
        });
        
        const result = await response.json();
        
        if (result.status === 'success' && result.data) {
            const messageId = result.data.message_id;
            
            // Poll for the response
            await pollForMessage(currentConversationId, messageId);
        } else {
            throw new Error(result.error || 'Failed to send message');
        }
    } catch (error) {
        console.error('Send followup error:', error);
        throw error;
    }
}

// Poll for message response
async function pollForMessage(conversationId, messageId, maxAttempts = 30) {
    let attempts = 0;
    
    // Show loading message
    const loadingId = addMessage('Thinking...', 'assistant', true);
    
    while (attempts < maxAttempts) {
        try {
            const response = await fetch(`/api/genie/conversations/${conversationId}/messages/${messageId}`);
            const result = await response.json();
            
            if (result.status === 'success' && result.data) {
                const message = result.data;
                
                // Debug: Log the full message structure
                console.log('Genie message received:', JSON.stringify(message, null, 2));
                
                // Check if message is complete
                if (message.status === 'COMPLETED' || message.status === 'FAILED') {
                    // Remove loading message
                    removeMessage(loadingId);
                    
                    if (message.status === 'COMPLETED') {
                        // Genie returns the response in attachments[0].query.description
                        let responseContent = '';
                        
                        // Extract Genie's response from attachment description
                        if (message.attachments && message.attachments.length > 0) {
                            const firstAttachment = message.attachments[0];
                            if (firstAttachment.query && firstAttachment.query.description) {
                                responseContent = firstAttachment.query.description;
                                console.log('Using attachment description:', responseContent);
                            }
                        }
                        
                        // Display Genie's text response
                        if (responseContent) {
                            addMessage(responseContent, 'assistant');
                        } else {
                            // Fallback if no description
                            console.log('No description found in attachment');
                            addMessage('Let me show you the results...', 'assistant');
                        }
                        
                        // Check for attachments (query results)
                        if (message.attachments && message.attachments.length > 0) {
                            for (const attachment of message.attachments) {
                                if (attachment.query && attachment.query.statement_id) {
                                    // Use attachment_id for fetching results
                                    const attachmentId = attachment.attachment_id || attachment.id;
                                    await fetchQueryResult(conversationId, messageId, attachmentId);
                                }
                            }
                        }
                        
                        // Fetch and display follow-up questions from Genie
                        await fetchFollowUpQuestions(conversationId, messageId);
                    } else {
                        // Failed status
                        addMessage('Sorry, I encountered an error processing your request.', 'error');
                    }
                    
                    return;
                }
            }
            
            // Wait before next attempt
            await new Promise(resolve => setTimeout(resolve, 1000));
            attempts++;
            
        } catch (error) {
            console.error('Poll error:', error);
            attempts++;
        }
    }
    
    // Timeout
    removeMessage(loadingId);
    addMessage('Request timed out. Please try again.', 'error');
}

// Fetch query results
async function fetchQueryResult(conversationId, messageId, attachmentId) {
    try {
        const response = await fetch(`/api/genie/conversations/${conversationId}/messages/${messageId}/query-result/${attachmentId}`);
        const result = await response.json();
        
        console.log('Fetch query result response:', result);
        
        if (result.status === 'success' && result.data) {
            const queryData = result.data;
            console.log('Query data:', queryData);
            
            // Display query results as a table - pass the entire statement_response to access both manifest and result
            if (queryData.statement_response) {
                console.log('Statement response:', queryData.statement_response);
                displayQueryResults(queryData.statement_response);
            } else if (queryData.result) {
                console.log('Direct result:', queryData.result);
                displayQueryResults(queryData);
            } else {
                console.log('No result found in expected locations');
            }
        }
    } catch (error) {
        console.error('Fetch query result error:', error);
    }
}

// Fetch follow-up questions from Genie
async function fetchFollowUpQuestions(conversationId, messageId) {
    try {
        const response = await fetch(`/api/genie/conversations/${conversationId}/messages/${messageId}`);
        const result = await response.json();
        
        if (result.status === 'success' && result.data) {
            const message = result.data;
            
            console.log('Checking for follow-up questions:', message);
            
            // Genie may provide follow-up questions in different fields
            const followUps = message.suggested_followups || 
                            message.followup_questions || 
                            message.suggested_questions ||
                            (message.attachments && message.attachments[0]?.suggested_followups) ||
                            [];
            
            if (followUps && followUps.length > 0) {
                console.log('Found follow-up questions:', followUps);
                displayFollowUpQuestions(followUps);
            } else {
                console.log('No follow-up questions found in message');
            }
        }
    } catch (error) {
        console.error('Fetch follow-up questions error:', error);
    }
}

// Display query results as table
function displayQueryResults(statementResponse) {
    console.log('Display query results called with:', statementResponse);
    
    // Extract data from the result object
    const data = statementResponse.result?.data_array || statementResponse.data_array || [];
    
    if (!data || data.length === 0) {
        console.log('No data_array or empty data');
        return;
    }
    
    // Extract schema from manifest
    let columns = [];
    if (statementResponse.manifest && statementResponse.manifest.schema && statementResponse.manifest.schema.columns) {
        columns = statementResponse.manifest.schema.columns;
        console.log('Found columns in manifest.schema.columns:', columns);
    } else if (statementResponse.schema && statementResponse.schema.columns) {
        columns = statementResponse.schema.columns;
        console.log('Found columns in schema.columns:', columns);
    } else if (statementResponse.columns) {
        columns = statementResponse.columns;
        console.log('Found columns directly:', columns);
    }
    
    console.log('Extracted columns:', columns);
    
    // If no schema found, try to infer from first data row
    if (columns.length === 0 && data.length > 0) {
        console.log('WARNING: No schema found, inferring from data');
        columns = data[0].map((_, index) => ({ name: `Column ${index + 1}` }));
    }
    
    // Create table HTML with better formatting
    let tableHtml = '<div class="query-result">';
    tableHtml += '<div class="query-result-header">📊 Query Results</div>';
    tableHtml += '<div class="table-container"><table class="results-table"><thead><tr>';
    
    // Add headers with proper formatting
    columns.forEach(col => {
        // Clean up column names (remove underscores, capitalize)
        const colName = typeof col === 'string' ? col : (col.name || 'Unknown');
        const cleanName = colName
            .replace(/_/g, ' ')
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
        tableHtml += `<th>${cleanName}</th>`;
    });
    tableHtml += '</tr></thead><tbody>';
    
    // Add rows (limit to 20 for display)
    const displayRows = data.slice(0, 20);
    displayRows.forEach((row, index) => {
        tableHtml += `<tr class="${index % 2 === 0 ? 'even' : 'odd'}">`;
        row.forEach(cell => {
            // Format cell values
            let displayValue = cell;
            if (cell === null || cell === undefined) {
                displayValue = '<span class="null-value">-</span>';
            } else if (typeof cell === 'number') {
                // Format numbers with commas
                displayValue = cell.toLocaleString();
            } else if (typeof cell === 'string' && cell.length > 100) {
                // Truncate long strings
                displayValue = cell.substring(0, 100) + '...';
            }
            tableHtml += `<td>${displayValue}</td>`;
        });
        tableHtml += '</tr>';
    });
    
    tableHtml += '</tbody></table></div>';
    
    // Row count info
    if (data.length > 20) {
        tableHtml += `<div class="row-count">Showing 20 of ${data.length} rows</div>`;
    } else {
        tableHtml += `<div class="row-count">${data.length} row${data.length !== 1 ? 's' : ''}</div>`;
    }
    
    tableHtml += '</div>';
    
    // Add as a separate message
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-content">
            ${tableHtml}
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Display follow-up questions
function displayFollowUpQuestions(followUps) {
    if (!followUps || followUps.length === 0) return;
    
    // Create follow-up questions HTML
    let followUpHtml = '<div class="followup-questions">';
    followUpHtml += '<div class="followup-header">💡 Related questions you can ask:</div>';
    followUpHtml += '<div class="followup-buttons">';
    
    // Limit to 3 follow-up questions
    followUps.slice(0, 3).forEach(question => {
        const questionText = typeof question === 'string' ? question : question.text || question.question || question.content;
        if (questionText) {
            // Escape quotes and create button
            const escapedText = questionText.replace(/'/g, "\\'").replace(/"/g, "&quot;");
            followUpHtml += `<button class="followup-btn" onclick="sendSampleQuestion('${escapedText}')">${questionText}</button>`;
        }
    });
    
    followUpHtml += '</div></div>';
    
    // Add as a separate message
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-content">
            ${followUpHtml}
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add message to chat
function addMessage(content, type, isLoading = false) {
    // Remove empty state if present
    const emptyState = chatMessages.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    const messageId = `msg-${Date.now()}-${Math.random()}`;
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.id = messageId;
    
    const avatar = type === 'user' ? 'U' : type === 'error' ? '⚠️' : 'AI';
    const bgColor = type === 'error' ? 'background-color: var(--error);' : '';
    
    if (isLoading) {
        messageDiv.innerHTML = `
            <div class="message-avatar" style="${bgColor}">${avatar}</div>
            <div class="message-content">
                <div class="loading">
                    <div class="spinner"></div>
                    <span>${content}</span>
                </div>
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="message-avatar" style="${bgColor}">${avatar}</div>
            <div class="message-content">
                ${formatMessageContent(content)}
                <div class="message-time">${new Date().toLocaleTimeString()}</div>
            </div>
        `;
    }
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    
    return messageId;
}

// Remove message by ID
function removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.remove();
    }
}

// Format message content (handle markdown-like formatting)
function formatMessageContent(content) {
    // Simple formatting: convert newlines to <br>
    return content.replace(/\n/g, '<br>');
}

// Scroll to bottom of chat
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Set processing state
function setProcessing(processing) {
    isProcessing = processing;
    sendBtn.disabled = processing;
    chatInput.disabled = processing;
    sendBtn.textContent = processing ? 'Sending...' : 'Send';
}

// Send sample question (called from buttons)
function sendSampleQuestion(question) {
    chatInput.value = question;
    chatForm.dispatchEvent(new Event('submit'));
}

// Reset chat and start new conversation
function resetChat() {
    // Reset conversation ID
    currentConversationId = null;
    
    // Clear chat messages
    chatMessages.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">💬</div>
            <h3 class="empty-state-title">Start a Conversation</h3>
            <p>Ask me about product analysis and insights!</p>
            <div style="margin-top: 1rem; display: flex; flex-direction: column; gap: 0.5rem; align-items: center;">
                <button class="btn btn-secondary" onclick="sendSampleQuestion('How many products were created each month ?')">
                    Products created by month
                </button>
                <button class="btn btn-secondary" onclick="sendSampleQuestion('What are the different ingredients types available in the ingredients master ?')">
                    Ingredient types available
                </button>
                <button class="btn btn-secondary" onclick="sendSampleQuestion('What is the average weight of packaging components')">
                    Avg packaging weight
                </button>
            </div>
        </div>
    `;
    
    // Clear input
    chatInput.value = '';
    
    // Reset processing state
    setProcessing(false);
    
    console.log('Chat reset - ready for new conversation');
}

// Make available globally
window.sendSampleQuestion = sendSampleQuestion;
window.resetChat = resetChat;

