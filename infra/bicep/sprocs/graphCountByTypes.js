/**
 * Cosmos DB stored procedure: graphCountByTypes
 *
 * Runs server-side within a single logical partition and counts documents
 * grouped by their subtype field:
 *   - type == "component"  → grouped by componentType
 *   - type == "edge"       → grouped by edgeType
 *
 * Returns a single JSON object:
 * {
 *   "componentCounts": { "<componentType>": <n>, … },
 *   "edgeCounts":      { "<edgeType>": <n>, … },
 *   "totalComponents": <n>,
 *   "totalEdges":      <n>
 * }
 *
 * The procedure handles continuation tokens internally so it works
 * correctly even when the partition contains more documents than a
 * single query page can return.
 */
// @ts-check
function graphCountByTypes() {
    var context = getContext();
    var collection = context.getCollection();
    var response = context.getResponse();

    var componentCounts = {};
    var edgeCounts = {};

    // Phase 1: count components
    queryByType("component", "componentType", componentCounts, function () {
        // Phase 2: count edges (after components finish)
        queryByType("edge", "edgeType", edgeCounts, function () {
            // Both phases done — build result
            var totalComponents = sumValues(componentCounts);
            var totalEdges = sumValues(edgeCounts);

            response.setBody({
                componentCounts: componentCounts,
                edgeCounts: edgeCounts,
                totalComponents: totalComponents,
                totalEdges: totalEdges
            });
        });
    });

    /**
     * Page through all documents of a given type and tally counts by subtype.
     * @param {string} docType        - "component" or "edge"
     * @param {string} subtypeField   - "componentType" or "edgeType"
     * @param {Object} counts         - accumulator object { subtype: count }
     * @param {function} callback     - called when all pages are consumed
     */
    function queryByType(docType, subtypeField, counts, callback) {
        var query = {
            query: "SELECT c." + subtypeField + " AS subtype FROM c WHERE c.type = @type",
            parameters: [{ name: "@type", value: docType }]
        };
        fetchPage(query, counts, undefined, callback);
    }

    /**
     * Fetch a single page and recurse with the continuation token.
     */
    function fetchPage(query, counts, continuation, callback) {
        var options = { continuation: continuation };
        var accepted = collection.queryDocuments(
            collection.getSelfLink(),
            query,
            options,
            function (err, docs, responseOptions) {
                if (err) throw err;

                for (var i = 0; i < docs.length; i++) {
                    var subtype = docs[i].subtype;
                    if (subtype) {
                        counts[subtype] = (counts[subtype] || 0) + 1;
                    }
                }

                if (responseOptions.continuation) {
                    fetchPage(query, counts, responseOptions.continuation, callback);
                } else {
                    callback();
                }
            }
        );

        if (!accepted) {
            // Query was not accepted (budget exhausted).  Return partial result
            // so the caller can retry.
            throw new Error("queryDocuments was not accepted by the server. Partition may be too large.");
        }
    }

    /**
     * Sum all values in an object.
     */
    function sumValues(obj) {
        var total = 0;
        for (var key in obj) {
            if (obj.hasOwnProperty(key)) {
                total += obj[key];
            }
        }
        return total;
    }
}
