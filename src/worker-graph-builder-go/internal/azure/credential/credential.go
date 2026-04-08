// Package credential provides Azure Managed Identity authentication via the
// official Azure SDK for Go (azidentity).
package credential

import (
	"fmt"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore"
	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
)

// New creates an Azure Managed Identity credential backed by the official
// azidentity SDK. Pass a non-empty clientID for a user-assigned managed
// identity; pass "" for system-assigned.
//
// The returned azcore.TokenCredential is accepted by all Azure SDK clients
// (azcosmos, aznamespaces, etc.) and handles token caching and refresh
// automatically.
func New(clientID string) (azcore.TokenCredential, error) {
	opts := &azidentity.ManagedIdentityCredentialOptions{}
	if clientID != "" {
		opts.ID = azidentity.ClientID(clientID)
	}
	cred, err := azidentity.NewManagedIdentityCredential(opts)
	if err != nil {
		return nil, fmt.Errorf("create managed identity credential: %w", err)
	}
	return cred, nil
}
