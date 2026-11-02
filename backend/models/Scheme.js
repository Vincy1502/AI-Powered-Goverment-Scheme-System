const mongoose = require("mongoose");

const schemeSchema = new mongoose.Schema({

    scheme_name: {
        type: String,
        required: true
    },

    parent_scheme: {
        type: String
    },

    ministry: {
        type: String
    },

    department: {
        type: String
    },

    objectives: {
        type: [String]
    },

    benefits: {
        type: mongoose.Schema.Types.Mixed
    },

    eligibility_criteria: {
        type: [String]
    },

    application_process: {
        type: mongoose.Schema.Types.Mixed
    },

    documents_required: {
        type: [String]
    },

    official_links: {
        type: mongoose.Schema.Types.Mixed
    }

});

module.exports = mongoose.model("Scheme", schemeSchema);