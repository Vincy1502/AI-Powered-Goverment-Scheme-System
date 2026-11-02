/**
 * SAFETY NOTICE:
 * This legacy script originally deleted every Scheme document and imported
 * data from a separate reference-project directory. Do not run that script
 * against the current GovScheme AI database. The project now reads its scheme
 * catalogue from MongoDB Atlas and does not require this import script.
 */
console.error("Blocked: this legacy import script is disabled because its original version deleted the live schemes collection and used a separate reference dataset.");
console.error("No database connection was opened and no data was changed.");
process.exitCode = 1;
