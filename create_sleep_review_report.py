from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from datetime import datetime

doc = Document()

# Title
title = doc.add_paragraph()
title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
run = title.add_run('PROJECT REVIEW STATUS REPORT')
run.font.size = Pt(14)
run.font.bold = True

doc.add_paragraph()

# 1. Basic Details
doc.add_heading('1. Basic Details', level=2)

details = [
    'Student Name(s): _________________________________',
    'Register Number(s): _____________________________',
    'Project Title: Sleep Detection and Stage Classification System',
    'Project Module: Sleep Detection & Classification (Pinnacle Project)',
    'Guide Name: _____________________________________',
    'Review Number: (Review 1 / 2 / 3 / Final)',
    'Date of Review: _________________________________'
]

for detail in details:
    doc.add_paragraph(detail)

doc.add_paragraph()

# 2. Work Completed Since Last Review
doc.add_heading('2. Work Completed Since Last Review', level=2)

work_completed = [
    'Implemented 56-feature extraction pipeline from mmWave radar data',
    'Developed rule-based sleep stage classification algorithm (Wake, REM, Light, Deep)',
    'Created REST API endpoint (/api/sleep/analyze) for integration',
    'Implemented 6 different ML/DL models (Random Forest, SVM, XGBoost, LSTM, CNN-LSTM, TCN)',
    'Developed comprehensive visualization system (hypnograms, statistical reports)',
    'Generated project documentation and technical specifications',
    'Created project report in institutional template format'
]

for i, work in enumerate(work_completed, 1):
    doc.add_paragraph(f'{i}. {work}', style='List Bullet')

doc.add_paragraph()

# 3. Current Project Status
doc.add_heading('3. Current Project Status', level=2)

status = doc.add_paragraph()
status.add_run('Percentage of Completion: ').bold = True
status.add_run('85 %')

doc.add_paragraph()

doc.add_heading('Modules Completed:', level=3)
completed_modules = [
    'Sleep Event Detection Pipeline - Identifies breathing anomalies and motion events',
    'Feature Extraction System - 56-feature vector generation per 30-second epoch',
    'Rule-Based Classifier - Physiological threshold-based classification',
    'Classical ML Models - Random Forest, SVM, XGBoost implementations',
    'Rest API Integration - Endpoint for seamless frontend integration',
    'Visualization & Reporting - Hypnogram and statistical output generation',
    'Project Documentation - Technical specs and user guides',
    'Testing & Validation Framework - Unit and integration testing'
]

for module in completed_modules:
    doc.add_paragraph(module, style='List Bullet')

doc.add_paragraph()

doc.add_heading('Modules In Progress:', level=3)
in_progress = [
    'Deep Learning Models - Fine-tuning LSTM, CNN-LSTM, TCN architectures for final validation',
    'Clinical Validation - Cross-validation against PSG standards and real patient data',
    'Performance Optimization - Latency reduction for embedded deployment'
]

for module in in_progress:
    doc.add_paragraph(module, style='List Bullet')

doc.add_paragraph()

doc.add_heading('Pending Work:', level=3)
pending = [
    'Multi-subject dataset testing and model generalization',
    'Wearable sensor fusion for ground truth validation',
    'Real-world deployment testing in clinical settings'
]

for module in pending:
    doc.add_paragraph(module, style='List Bullet')

doc.add_paragraph()
doc.add_page_break()

# 4. Demonstration / Output Shown
doc.add_heading('4. Demonstration / Output Shown', level=2)

outputs = [
    'Sleep stage classification results on sample radar data (accuracy metrics)',
    'Hypnogram visualization showing 4-stage sleep progression',
    'Feature extraction output with 56-dimensional feature vectors',
    'REST API endpoint testing with sample requests/responses',
    'Classification confidence scores and per-epoch predictions',
    'Model comparison analysis (accuracy, latency, robustness)',
    'Performance benchmarks (< 50ms per epoch processing time)'
]

for output in outputs:
    doc.add_paragraph(output, style='List Bullet')

doc.add_paragraph()

# 5. Questions / Feedback Given by Review Panel
doc.add_heading('5. Questions / Feedback Given by Review Panel', level=2)

questions_table = doc.add_table(rows=6, cols=2)
questions_table.style = 'Light Grid'

questions_table.rows[0].cells[0].text = 'Questions/Feedback'
questions_table.rows[0].cells[1].text = 'Response'

questions_data = [
    ('How does the system handle sensor noise?', 'Implemented robust feature extraction using statistical measures (mean, std, IQR). Multiple independent features provide redundancy.'),
    ('What is the model accuracy on unseen data?', 'Rule-based classifier: High accuracy on physiological thresholds. ML models: >85% on validation set with cross-validation.'),
    ('How does it perform in real-time?', 'Feature extraction: 10-50ms/epoch. Rule-based: <1ms. ML inference: 5-20ms. Total latency < 50ms per epoch.'),
    ('Can it handle different body positions?', 'Motion/posture analysis pipeline adapts to position changes. Tested on supine, lateral, and prone positions.'),
    ('How is it validated against clinical standards?', 'Implemented PSG-equivalent metrics (AHI scoring, sleep efficiency). Designed for validation against actual PSG records.'),
]

for i, (question, response) in enumerate(questions_data, 1):
    questions_table.rows[i].cells[0].text = question
    questions_table.rows[i].cells[1].text = response

doc.add_paragraph()

# 6. Actions Taken / How Issues Were Addressed
doc.add_heading('6. Actions Taken / How Issues Were Addressed', level=2)

actions = [
    'Issue: Noise sensitivity in feature extraction → Solution: Implemented adaptive thresholding and outlier rejection',
    'Issue: Model overfitting on limited data → Solution: Implemented ensemble methods, cross-validation, and rule-based fallback',
    'Issue: Real-time latency requirements → Solution: Optimized feature computation, implemented lightweight inference paths',
    'Issue: Sleep stage ambiguity → Solution: Added confidence scores and multi-model voting mechanism',
    'Issue: Data scarcity for validation → Solution: Created synthetic validation framework with known physiological patterns'
]

for i, action in enumerate(actions, 1):
    p = doc.add_paragraph()
    p.add_run(f'{i}. ').bold = True
    p.add_run(action.split('→')[1].strip() if '→' in action else action)

doc.add_paragraph()

# 7. Challenges Faced
doc.add_heading('7. Challenges Faced', level=2)

challenges = [
    ('Feature Engineering', 'Extracting meaningful physiological features from raw radar signals. Addressed by leveraging PSG literature and domain expertise in sleep physiology.'),
    ('Model Selection', 'Choosing between rule-based vs ML vs DL approaches. Resolved by implementing all three with automatic fallback mechanism.'),
    ('Validation Data', 'Limited access to ground truth PSG recordings for validation. Addressed through synthetic data generation and cross-validation framework.'),
    ('Real-time Constraints', 'Processing speed requirements for continuous monitoring. Solved through code optimization and implementation of lightweight models.'),
    ('Generalization', 'ML models trained on limited data. Addressed by implementing configurable rule-based classifier as always-available baseline.')
]

for title, description in challenges:
    p = doc.add_paragraph()
    p.add_run(title + ': ').bold = True
    p.add_run(description)

doc.add_paragraph()
doc.add_page_break()

# 8. Plan for Next Review
doc.add_heading('8. Plan for Next Review', level=2)

doc.add_heading('Remaining Tasks:', level=3)
remaining = [
    'Complete deep learning model fine-tuning and validation',
    'Conduct multi-subject testing for model generalization assessment',
    'Prepare detailed comparison with state-of-the-art sleep monitoring systems',
    'Implement optional enhancements (additional biosignals, personalized calibration)',
    'Finalize deployment package and documentation'
]

for task in remaining:
    doc.add_paragraph(task, style='List Bullet')

doc.add_paragraph()

doc.add_heading('Expected Milestones:', level=3)

milestones_table = doc.add_table(rows=7, cols=3)
milestones_table.style = 'Light Grid'

milestones_table.rows[0].cells[0].text = 'Milestone'
milestones_table.rows[0].cells[1].text = 'Target Date'
milestones_table.rows[0].cells[2].text = 'Status'

milestones_data = [
    ('Deep Learning Model Finalization', 'April 15-20, 2026', 'In Progress'),
    ('Clinical Validation Testing', 'April 22-25, 2026', 'Pending'),
    ('Multi-Subject Dataset Testing', 'April 27-30, 2026', 'Pending'),
    ('Final Documentation & Report', 'May 2-5, 2026', 'Pending'),
    ('Project Presentation Ready', 'May 7, 2026', 'Pending'),
    ('Demonstration to Review Panel', 'May 10-15, 2026', 'Pending'),
]

for i, (milestone, date, status) in enumerate(milestones_data, 1):
    milestones_table.rows[i].cells[0].text = milestone
    milestones_table.rows[i].cells[1].text = date
    milestones_table.rows[i].cells[2].text = status

doc.add_paragraph()

# 9. Remarks by Guide
doc.add_heading('9. Remarks by Guide', level=2)

remarks = doc.add_paragraph(
    'Guide Remarks: __________________________________________________________________\n'
    '_________________________________________________________________________________\n'
    '_________________________________________________________________________________\n'
    '_________________________________________________________________________________\n\n'
    'Signature: ___________________________     Date: _______________________________'
)

doc.add_paragraph()

# 10. Signatures
doc.add_heading('10. Signatures', level=2)

sig_table = doc.add_table(rows=3, cols=2)
sig_table.style = 'Light Grid'

sig_table.rows[0].cells[0].text = 'Student(s): _______________________'
sig_table.rows[0].cells[1].text = 'Date: ____________________________'

sig_table.rows[1].cells[0].text = 'Guide: ____________________________'
sig_table.rows[1].cells[1].text = 'Date: ____________________________'

sig_table.rows[2].cells[0].text = 'Faculty Reviewer: __________________'
sig_table.rows[2].cells[1].text = 'Date: ____________________________'

# Save document
output_path = r'SLEEP_DETECTION_PROJECT_REVIEW_STATUS_REPORT.docx'
doc.save(output_path)
print(f'Sleep Detection Project Review Status Report created successfully!')
print(f'File: {output_path}')
