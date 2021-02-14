# Weights for each TEAP competency group and overall module

teap_weights = {
    '1.1': 0.6,
    '1.2': 1.0,
    '1.3': 0.3,
    '1': 2.0,
    '2.1': 0.5,
    '2.2': 1.0,
    '2.3': 0.4,
    '2.4': 1.0,
    '2.5': 0.7,
    '2.6': 0.5,
    '2': 4.1,
    '3.1': 1.4,
    '3.2': 0.4,
    '3.3': 1.0,
    '3.4': 1.0,
    '3.5': 0.4,
    '3': 4.2,
    '4.1': 2,
    '4.2': 0.5,
    '4.3': 0.2,
    '4.4': 0.5,
    '4.5': 0.5,
    '4.6': 0.5,
    '4.7': 0.2,
    '4': 4.4,
    '5.1': 1.0,
    '5.2': 0.5,
    '5.3': 1.0,
    '5.4': 0.5,
    '5.5': 0.75,
    '5': 3.75,
    '6.1': 1.0,
    '6.2': 1.0,
    '6.3': 0.7,
    '6.4': 0.7,
    '6.5': 1.2,
    '6.6': 2,
    '6': 6.6 * 35 / 50,  # Manually adjusted to handle the lack of level 3's
    '7.1': 0.4,
    '7.2': 0.6,
    '7.3': 0.4,
    '7.4': 0.5,
    '7': 1.9,
    '8.1': 1.5,
    '8.2': 1.0,
    '8.3': 1.0,
    '8.4': 1.0,
    '8.5': 0.5,
    '8.6': 0.5,
    '8.7': 0.5,
    '8': 5
}

# Expected points to be at any point in the program. Key is years, y is an array of expected points after index +1 years
# For example, teap_required_points['4'][2] would be the expected number of points a registrar would have after 3 years
# in a four year program
teap_required_points = {
    '3': [0, 133 + 1 / 3, 266 + 2 / 3, 400],
    '4': [0, 66.66666667, 133.3333333, 267.0319635, 400],
    '5': [0, 44 + 4 / 9, 88 + 8 / 9, 133.6986301, 267.0319635, 400]
}

# Labels for each competency group. These are unofficial
teap_categories = {
    '1': {
        '1': 'General treatments',
        '2': 'Radiobiology',
        '3': 'Clinical professionalism'
    },
    '2': {
        '1': 'Principal requirements',
        '2': 'Room shielding',
        '3': 'Radiation detection',
        '4': 'Radioactive sources',
        '5': 'Medical, occupational, public',
        '6': 'Incidents & Accidents'
    },
    '3':
        {
            '1': 'Dosimetry systems',
            '2': 'Ancillary components',
            '3': 'Measure dose',
            '4': 'Relative dosimetry',
            '5': 'In-vivo',
        },
    '4':
        {
            '1': 'Linacs',
            '2': 'MLC',
            '3': 'Immobilisation',
            '4': 'IGRT',
            '5': 'CT',
            '6': 'kV',
            '7': 'OIS'
        },
    '5':
        {
            '1': 'TPS',
            '2': 'Imaging',
            '3': 'Planning',
            '4': 'Specialist / new techniques',
            '5': 'Plan QA'
        },
    '6':
        {
            '1': 'HDR systems',
            '2': 'Calibration',
            '3': 'TPS',
            '4': 'Imaging',
            '5': 'HDR',
            '6': 'LDR',
        },
    '7':
        {
            '1': 'Professionalism',
            '2': 'Management',
            '3': 'Procurement',
            '4': 'Teaching'
        },
    '8':
        {
            '1': 'Image quality',
            '2': 'CT',
            '3': 'MRI',
            '4': 'PET',
            '5': 'Fluoroscopy',
            '6': 'Ultrasound',
            '7': 'SPECT'
        }
}
